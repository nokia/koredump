# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2022-04-27
### Changed
- REST API access now requires valid Kubernetes token. `koredumpctl` tool can take it from `oc whoami --show-token` command output in Red Hat OCP.
- Switch container base image to Red Hat UBI8. Container build is reworked and python dependencies now installed with pip. Container images are now built to amd64, arm64, ppc64le and s390x.
- Collection of core files from given namespaces only, see Helm chart `filter.namespaceRegex` variable. The variable can be defined when koredump is installed into Kubernetes cluster.
- `koredumpctl` tool shows more information in list command output.
- `koredumpctl` tool can automatically connect to exposed REST API, that was exposed with OCP routes, instead of doing port forward.
### Fixed
- Speed up and improve reading of systemd journal.
- Fixes to `koredumpctl` error handling.
- Fixes to HTTP logging in containers.

## [0.3.4] - 2022-03-02
### Changed
- Container image repository is now ghcr.io/nokia/koredump
- Improve metadata parsing in Red Hat OCP.
### Fixed
- Fix for SELinux enforcing mode.

## [0.3.3] - 2022-02-23
### Changed
- Improve journal log reading reliability in koremonitor.
- Set CPU and memory requests and limits in Helm chart.
- Tweaks to tools and code.

## [0.3.2] - 2022-02-18
### Changed
- Drop "koredump" prefix from git repository tags.

## [0.3.1] - 2022-02-18
### Changed
- Use one container image instead of two.

## [0.3.0] - 2022-02-17
### Added
- Initial release at GitHub.

[unreleased]: https://github.com/nokia/koredump/compare/0.4.0...HEAD
[0.4.0]: https://github.com/nokia/koredump/compare/0.3.4...0.4.0
[0.3.4]: https://github.com/nokia/koredump/compare/0.3.3...0.3.4
[0.3.3]: https://github.com/nokia/koredump/compare/0.3.2...0.3.3
[0.3.2]: https://github.com/nokia/koredump/compare/koredump-0.3.1...0.3.2
[0.3.1]: https://github.com/nokia/koredump/compare/koredump-0.3.0...koredump-0.3.1
[0.3.0]: https://github.com/nokia/koredump/releases/tag/koredump-0.3.0
