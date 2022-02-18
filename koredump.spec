# Copyright (C) 2022 Nokia
# Licensed under the MIT License
# SPDX-License-Identifier: MIT

Name:           koredump
Version:        0.3.1
Release:        1%{?dist}
Summary:        Kubernetes coredump REST API

License:        MIT
URL:            https://github.com/nokia/koredump

Source0:        app.py
Source1:        koremonitor.py
Source2:        koredumpctl
Source3:        LICENSE
Source4:        README.md

Requires:       python3-cachetools
Requires:       python3-certifi
Requires:       python3-cffi
Requires:       python3-dateutil
Requires:       python3-flask
Requires:       python3-flask-httpauth
Requires:       python3-google-auth
Requires:       python3-gunicorn
Requires:       python3-inotify
Requires:       python3-jinja2
Requires:       python3-marshmallow
Requires:       python3-pyxattr
Requires:       python3-requests
Requires:       python3-requests-oauthlib
Requires:       python3-systemd
Requires:       python3-urllib3
Requires:       python3-websocket-client
Requires:       python3-werkzeug
Requires:       python3-yaml
Requires:       lz4
Requires:       zstd
Requires:       xz
BuildArch:      noarch

%description
Kubernetes coredump REST API.


%package utils
Summary:        Kubernetes coredump REST API utilities
Requires:       jq
Requires:       /usr/bin/getopt
Requires:       /usr/bin/tput

%description utils
Kubernetes coredump REST API utilities.


%prep
cp %{SOURCE0} %{SOURCE1} %{SOURCE2} %{SOURCE3} %{SOURCE4} .
sed -i -e "s/^version=.*/version=%{version}/" koredumpctl


%build


%install
rm -rf $RPM_BUILD_ROOT
install -Dpm644 app.py $RPM_BUILD_ROOT%{_libexecdir}/koredump/app.py
install -Dpm755 koremonitor.py $RPM_BUILD_ROOT%{_bindir}/koremonitor.py
install -Dpm755 koredumpctl $RPM_BUILD_ROOT%{_bindir}/koredumpctl


%files
%license LICENSE
%doc README.md
%{_libexecdir}/koredump/app.py
%{_bindir}/koremonitor.py


%files utils
%{_bindir}/koredumpctl
