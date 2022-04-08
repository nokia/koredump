# Copyright (C) 2022 Nokia
# Licensed under the MIT License
# SPDX-License-Identifier: MIT

FROM registry.access.redhat.com/ubi8/ubi:8.5 AS base
MAINTAINER Nokia

ARG VERSION=0.3.4

# Required OpenShift Labels
LABEL name="koredump" \
      maintainer="tommi.t.rantala@nokia.com" \
      vendor="Nokia" \
      version="$VERSION" \
      release="1" \
      summary="Kubernetes coredump REST API" \
      description="Kubernetes coredump REST API" \
      io.k8s.description="Kubernetes coredump REST API" \
      io.k8s.display-name="koredump" \
      url="https://github.com/nokia/koredump" \
      license="MIT"

# Licenses for OpenShift
COPY LICENSE /licenses

COPY requirements.txt /koredump/
COPY app.py /usr/libexec/koredump/
COPY koredumpctl /usr/bin/
COPY koremonitor.py /usr/bin/
RUN sed -i -e "s/^version=.*/version=${VERSION}/" /usr/bin/koredumpctl \
    && dnf upgrade -y --setopt=install_weak_deps=0 \
    && dnf install -y --setopt=install_weak_deps=0 --nodocs \
    gcc \
    libcap \
    pkg-config \
    python39-devel \
    python39-devel \
    python39-pip \
    python39-pycparser \
    python39-setuptools \
    python39-six \
    python39-wheel \
    shadow-utils \
    systemd-devel \
    jq \
    /usr/bin/getopt \
    /usr/bin/tput \
    lz4 \
    xz \
    zstd \
    && groupadd -g 900 koredump \
    && useradd -r -u 900 -g koredump -M -s /sbin/nologin koredump \
    && pip3 install --disable-pip-version-check --no-cache-dir -r /koredump/requirements.txt \
    && pip3 check \
    && rm /koredump/requirements.txt \
    && mv /usr/local/bin/gunicorn /usr/bin/ \
    && dnf remove -y \
    gcc \
    pkg-config \
    python39-devel \
    python39-pip \
    shadow-utils \
    systemd-devel \
    && dnf clean all

# Special copy of python3 executable with CAP_DAC_OVERRIDE, needed in DaemonSet
# containers to access core dump files and journal logs as non-root user.
RUN install --mode=0550 --group=koredump /usr/bin/python3 /usr/libexec/koredump/python3 \
    && setcap cap_dac_override+eip /usr/libexec/koredump/python3
