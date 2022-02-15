# Copyright (C) 2022 Nokia
# Licensed under the MIT License
# SPDX-License-Identifier: MIT

ARG BASE_IMAGE=fedora:35
FROM $BASE_IMAGE AS base
RUN sed -i -e 's|enabled=1|enabled=0|' /etc/yum.repos.d/fedora-{cisco-openh264,modular,updates-modular,updates-testing,updates-testing-modular}.repo
RUN dnf upgrade -y --setopt=install_weak_deps=0 && dnf clean all

# Build RPMs
FROM base AS builder
ARG VER
RUN dnf install -y --setopt=install_weak_deps=0 dnf-plugins-core rpm-build
COPY koredump-${VER}.tar.gz /rpmbuild/SOURCES/
COPY koredump.spec /rpmbuild/SPECS/
RUN dnf builddep -y --setopt=install_weak_deps=0 --spec /rpmbuild/SPECS/koredump.spec
RUN rpmbuild --define "_topdir /rpmbuild" -ba /rpmbuild/SPECS/koredump.spec

# Build container
FROM base
ARG PYPI_INDEX_URL=""

COPY --from=builder /rpmbuild/RPMS/*/*.rpm /tmp/
RUN dnf install -y --setopt=install_weak_deps=0 /tmp/*.rpm && rm /tmp/*.rpm \
    && dnf install -y --setopt=install_weak_deps=0 \
    python3-markupsafe \
    python3-pip \
    python3-pycparser \
    python3-setuptools \
    python3-six \
    shadow-utils \
    libcap \
    && groupadd -g 900 koredump \
    && useradd -r -u 900 -g koredump -M -s /sbin/nologin koredump \
    && dnf remove -y shadow-utils \
    && dnf clean all

COPY requirements.txt /koredump/
RUN pip3 install --disable-pip-version-check $PYPI_INDEX_URL -r /koredump/requirements.txt \
    && rm /koredump/requirements.txt \
    && dnf remove -y python3-pip

CMD ["/usr/bin/gunicorn", "--chdir=/usr/libexec/koredump", "app"]
