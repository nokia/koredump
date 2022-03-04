#!/bin/python3

"""
Copyright (C) 2022 Nokia
Licensed under the MIT License
SPDX-License-Identifier: MIT

Monitors for new core files in /var/lib/systemd/coredump/
Generates /koredump/index.json with data on available cores.
"""

import json
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime

import pyinotify
import xattr
from systemd import journal


class KoreMonitor(pyinotify.ProcessEvent):
    """
    Monitors for new core files in /var/lib/systemd/coredump/
    Generates /koredump/index.json with data on available cores.
    """

    def my_init(self, **kargs):
        self.logger = logging.getLogger(type(self).__name__)
        self.koredir = "/koredump"
        self.cores = {}
        self.systemd_corepath = "/var/lib/systemd/coredump/"
        self.MAX_CORES = 10000
        self.first_run = True

    def _load_index_json(self) -> dict:
        """
        Load index.json from disk.
        Metadata is stored on disk to allow to restore it after service crash or node reboot.
        """
        ret = {}
        try:
            index_path = os.path.join(self.koredir, "index.json")
            if not os.path.exists(index_path):
                return ret
            with open(index_path) as fp:
                ret = json.load(fp)
            self.logger.info("Read %d cores from %s", len(ret), index_path)
            for core_id in ret:
                self.logger.debug("%s", core_id)
            return ret
        except json.JSONDecodeError as ex:
            self.logger.warning("JSON error %s: %s", index_path, ex)
        except Exception as ex:
            self.logger.debug("Exception: %s", ex)

        try:
            # Problem with index.json? Delete it and recreate later.
            self.logger.info("Deleting %s", index_path)
            os.unlink(index_path)
        except Exception:
            pass
        return ret

    def load_index_json(self):
        self.cores = self._load_index_json()

    def save_index_json(self):
        """Save index.json to disk."""
        index_path = os.path.join(self.koredir, "index.json")
        index_path_tmp = f"{index_path}.tmp"
        try:
            with open(index_path_tmp, "w") as fp:
                json.dump(self.cores, fp)
            os.rename(index_path_tmp, index_path)
        except Exception as ex:
            self.logger.warning("Failed to generate %s: %s", index_path_tmp, ex)
        try:
            os.unlink(index_path_tmp)
        except Exception:
            pass

    def fmt_journal_entry(self, entry):
        """Format journal entry to allow JSON conversion."""
        if "__CURSOR" in entry:
            del entry["__CURSOR"]
        for key in ("MESSAGE_ID", "_BOOT_ID", "_MACHINE_ID"):
            entry[key] = entry[key].hex
        for (k, v) in entry.items():
            if isinstance(v, journal.Monotonic):
                entry[k] = str(v.timestamp)
            elif isinstance(v, datetime):
                entry[k] = v.isoformat() + "Z"
            elif not isinstance(v, (str, int)):
                self.logger.error(k, v)
        return entry

    def read_journal(self, core_path) -> bool:
        """
        Read systemd-coredump metadata for given core, from journal.
        Return true if entry found from journal.
        """
        journal_reader = journal.Reader()
        journal_reader.add_match(
            "MESSAGE_ID=fc2e22bc6ee647b6b90729ab34a250b1",
            f"COREDUMP_FILENAME={core_path}",
        )

        if not self.first_run:
            try:
                st = os.stat(core_path)
            except FileNotFoundError as ex:
                self.logger.warning("Failed to stat %s: %s", core_path, ex)
                return False
            journal_reader.seek_realtime(st.st_ctime)

        found = False
        for entry in journal_reader:
            if "COREDUMP_FILENAME" not in entry:
                continue
            core_id = os.path.basename(entry["COREDUMP_FILENAME"])
            if not core_id:
                continue
            if core_id not in self.cores:
                continue
            self.cores[core_id].update(self.fmt_journal_entry(entry))
            self.logger.info(
                "Core ID %s from journal, %d keys of metadata.",
                core_id,
                len(self.cores[core_id]),
            )
            found = True
        return found

    def read_systemd_xattrs(self, core_id, core_path):
        """
        Read xattrs stored by systemd-coredump.

        Example:
        ```
        $ getfattr --absolute-names -d /var/lib/systemd/coredump/*
        # file: /var/lib/systemd/coredump/core.python3.0.fe0148e99a2741c689f5b19dbbe5f89b.392481.1639840830000000.zst
        user.coredump.comm="python3"
        user.coredump.exe="/usr/bin/python3.10"
        user.coredump.gid="0"
        user.coredump.hostname="fedora"
        user.coredump.pid="392481"
        user.coredump.rlimit="18446744073709551615"
        user.coredump.signal="11"
        user.coredump.timestamp="1639840830000000"
        user.coredump.uid="0"
        ```
        """
        attrs = xattr.get_all(core_path, namespace=xattr.NS_USER)
        self.logger.debug("%s: %d xattrs.", core_path, len(attrs))
        for key, val in attrs:
            key = key.decode()
            if not key.startswith("coredump."):
                continue
            attr_name = key.replace("coredump.", "COREDUMP_").upper()
            if attr_name in self.cores[core_id]:
                continue
            try:
                self.cores[core_id][attr_name] = val.decode()
                if attr_name == "COREDUMP_TIMESTAMP":
                    ts = self.cores[core_id][attr_name]
                    if ts.endswith("000000"):
                        ts = ts[:-6]
                    self.cores[core_id][attr_name] = (
                        datetime.utcfromtimestamp(int(ts)).isoformat() + "Z"
                    )
                elif attr_name in (
                    "COREDUMP_GID",
                    "COREDUMP_PID",
                    "COREDUMP_SIGNAL",
                    "COREDUMP_UID",
                ):
                    self.cores[core_id][attr_name] = int(self.cores[core_id][attr_name])
            except ValueError:
                pass
            # self.logger.debug(" - %s: %s", attr_name, self.cores[core_id][attr_name])

    def read_cores(self):
        """
        Process any new core files.
        """
        dirty = False

        try:
            retry = 10
            for core_id in sorted(os.listdir(self.systemd_corepath)):
                if len(self.cores) >= self.MAX_CORES:
                    break
                if not core_id.startswith("core."):
                    continue
                if core_id in self.cores:
                    continue
                core_path = f"{self.systemd_corepath}{core_id}"

                dirty = True
                self.logger.info("New coredump: %s", core_path)
                self.cores[core_id] = {
                    "id": core_id,
                    "_systemd_coredump": True,
                    "_core_dir": self.systemd_corepath,
                }

                # Retry a few times, wait for systemd-coredump journal entries to become available.
                while retry > 0:
                    if self.read_journal(core_path):
                        break
                    retry -= 1
                    time.sleep(0.05)
                if not self.first_run:
                    retry = 10
                else:
                    retry = 1

                self.read_systemd_xattrs(core_id, core_path)

        except Exception as ex:
            self.logger.exception(ex)
            self.logger.debug("Exception: %s", ex)

        self.first_run = False

        # Cleanup cores that have been deleted from filesystem.
        def filter_deleted_cores(cores: dict) -> dict:
            nonlocal dirty
            newcores = {}
            for core_id in cores:
                core_path = os.path.join(cores[core_id]["_core_dir"], core_id)
                if os.path.exists(core_path):
                    newcores[core_id] = cores[core_id]
                else:
                    dirty = True
            return newcores

        self.cores = filter_deleted_cores(self.cores)

        if not dirty:
            return

        for core_id in self.cores:
            if "COREDUMP_CONTAINER_CMDLINE" in self.cores[core_id]:
                if match := re.match(
                    "/usr/bin/conmon .* -l /var/log/pods/[^/]+/([^/]+)/",
                    self.cores[core_id]["COREDUMP_CONTAINER_CMDLINE"],
                ):
                    self.cores[core_id]["container"] = match.group(1)

                if match := re.match(
                    r"/usr/bin/conmon .* -n (\S+)",
                    self.cores[core_id]["COREDUMP_CONTAINER_CMDLINE"],
                ):
                    name = match.group(1)
                    if name.startswith("k8s_"):
                        # Example: "-n k8s_console_console-84d757d6d8-2ppt5_openshift-console_4b9fafec-fa78-4274-ae14-6274f248a859_642"
                        #  0: k8s
                        #  1: console                                  # container
                        #  2: console-84d757d6d8-2ppt5                 # pod
                        #  3: openshift-console                        # namespace
                        #  4: 4b9fafec-fa78-4274-ae14-6274f248a859     # uid
                        #  5: 642                                      # restarts
                        #
                        split = name.split("_")
                        if len(split) == 6:
                            if "container" not in self.cores[core_id] and split[1]:
                                self.cores[core_id]["container"] = split[1]
                            if "pod" not in self.cores[core_id] and split[2]:
                                self.cores[core_id]["pod"] = split[2]
                            if "namespace" not in self.cores[core_id] and split[3]:
                                self.cores[core_id]["namespace"] = split[3]
                    else:
                        self.cores[core_id]["container"] = name

                if "_HOSTNAME" in self.cores[core_id]:
                    self.cores[core_id]["node"] = self.cores[core_id]["_HOSTNAME"]
                if (
                    "pod" not in self.cores[core_id]
                    and "COREDUMP_HOSTNAME" in self.cores[core_id]
                ):
                    self.cores[core_id]["pod"] = self.cores[core_id][
                        "COREDUMP_HOSTNAME"
                    ]

                if match := re.match(
                    "/usr/bin/conmon .*-b (/run/containers/storage/overlay-containers/[0-9a-fA-F]+/userdata)",
                    self.cores[core_id]["COREDUMP_CONTAINER_CMDLINE"],
                ):
                    try:
                        config_json_path = os.path.join(match.group(1), "config.json")
                        with open(config_json_path) as fp:
                            self.cores[core_id]["crio"] = json.load(fp)
                        self.cores[core_id]["image_name"] = self.cores[core_id]["crio"][
                            "annotations"
                        ]["io.kubernetes.cri-o.ImageName"]
                        if "namespace" not in self.cores[core_id]:
                            self.cores[core_id]["namespace"] = self.cores[core_id][
                                "crio"
                            ]["annotations"]["io.kubernetes.pod.namespace"]
                    except Exception as ex:
                        self.logger.debug("CRI-O config.json exception: %s", ex)

            else:
                # Assume the process was not running in container.
                if "_HOSTNAME" in self.cores[core_id]:
                    self.cores[core_id]["node"] = self.cores[core_id]["_HOSTNAME"]
            # Try to fill in the kubernetes node name if missing.
            if "node" not in self.cores[core_id]:
                if node_name := os.getenv("KOREDUMP_MY_NODE_NAME"):
                    # This variable set via our Helm charts.
                    self.cores[core_id]["node"] = node_name
                elif node_name := os.getenv("HOSTNAME"):
                    # When we are running in kubernetes container, $HOSTNAME != node name.
                    if not node_name.startswith("koredump-"):
                        self.cores[core_id]["node"] = node_name
            # Signal name comes from journal logs.
            # If we did not get it, try to add it from the signal number.
            if (
                "COREDUMP_SIGNAL_NAME" not in self.cores[core_id]
                and "COREDUMP_SIGNAL" in self.cores[core_id]
            ):
                try:
                    signum = int(self.cores[core_id]["COREDUMP_SIGNAL"])
                    self.cores[core_id]["COREDUMP_SIGNAL_NAME"] = signal.Signals(
                        signum
                    ).name
                except Exception as ex:
                    self.logger.debug("Signal name error: %s", ex)
            # If we failed to read timestamp from journal logs or xattrs, stat() the file.
            if "COREDUMP_TIMESTAMP" not in self.cores[core_id]:
                try:
                    core_path = os.path.join(self.cores[core_id]["_core_dir"], core_id)
                    st = os.stat(core_path)
                    self.cores[core_id]["COREDUMP_TIMESTAMP"] = (
                        datetime.utcfromtimestamp(int(st.st_mtime)).isoformat() + "Z"
                    )
                except Exception as ex:
                    self.logger.debug("stat(%s) exception: %s", core_path, ex)
            # Add CPU architecture metadata.
            # Assume all core files are generated on local machine.
            self.cores[core_id]["ARCH"] = os.uname().machine

        self.save_index_json()

    def process_IN_CREATE(self, event: pyinotify.Event):
        """
        Callback for inotify CREATE events.
        """
        self.logger.info("Inotify event %s path=%s", event.maskname, event.pathname)

    def process_IN_CLOSE_WRITE(self, event: pyinotify.Event):
        """
        Callback for inotify CLOSE_WRITE events.
        """
        self.logger.info("Inotify event %s path=%s", event.maskname, event.pathname)
        self.read_cores()

    def process_IN_DELETE(self, event: pyinotify.Event):
        """
        Callback for inotify DELETE events.
        """
        self.logger.info("Inotify event %s path=%s", event.maskname, event.pathname)
        self.read_cores()


if __name__ == "__main__":
    loglevel = logging.INFO
    if len(sys.argv) > 1 and sys.argv[1] == "-v":
        loglevel = logging.DEBUG
    logging.basicConfig(
        level=loglevel,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    koremonitor = KoreMonitor()
    if not os.path.exists(koremonitor.systemd_corepath):
        logging.critical(
            "Monitoring path does not exist: %s", koremonitor.systemd_corepath
        )
        exit(1)
    koremonitor.load_index_json()
    watch_manager = pyinotify.WatchManager()
    event_notifier = pyinotify.Notifier(watch_manager, koremonitor)
    watch_manager.add_watch(
        koremonitor.systemd_corepath,
        pyinotify.IN_CREATE | pyinotify.IN_CLOSE_WRITE | pyinotify.IN_DELETE,
    )
    logging.info("Start watching %s", koremonitor.systemd_corepath)
    koremonitor.read_cores()
    logging.info("Total %d cores available.", len(koremonitor.cores))
    event_notifier.loop()
