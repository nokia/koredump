#!/bin/bash
# Copyright (C) 2022 Nokia
# Licensed under the MIT License
# SPDX-License-Identifier: MIT
#
# This script tests koredump for example in Red Hat OCP:
# - Install koredump in kubernetes cluster.
# - Run pod to generate core dump.
# - Verify that core dump is visible and metadata was correctly collected.
#

project="koredump"
test_image_name="quay.io/rantala/pycore:latest"

red=$(tput setaf 1)
green=$(tput setaf 2)
#yellow=$(tput setaf 3)
bold=$(tput bold)
reset=$(tput sgr0)

function check_core_pattern() {
	if ! grep -q '^|/usr/lib/systemd/systemd-coredump ' /proc/sys/kernel/core_pattern; then
		printf "%s\n" "${red}Error: unsupported /proc/sys/kernel/core_pattern - must use systemd-coredump${reset}" >&2
		return 1
	fi
}
function cleanup_pycores() {
	if ls /var/lib/systemd/coredump/core.pycore.* &>/dev/null; then
		echo "Cleanup old pycore core files."
		sudo rm /var/lib/systemd/coredump/core.pycore.*
	fi
}
function delete_coretest_pod() {
	if kubectl get pod coretest &>/dev/null; then
		printf "%s\n" "${bold}kubectl delete pod coretest${reset}"
		kubectl delete pod coretest
		kubectl wait --for=delete pod coretest
	fi
}
function usage() {
	echo "Usage: $0 [args...]"
	echo
	echo "Optional arguments:"
	echo "       -U, --no-uninstall    Do not uninstall helm chart before and after testing."
	echo "                             Default: koredump is uninstalled before and after testing."
	echo
}
function print_hr() {
	printf "%s\n" "============================================================"
}
function helm_uninstall() {
	helm -n "$project" uninstall koredump || exit
	sleep 1
	echo "Waiting for koredump pods to terminate..."
	secs=300
	while [ "$(kubectl get pods -n "$project" -l app.kubernetes.io/name=koredump -o json | jq -r '.items | length')" -gt 0 ]; do
		sleep 1
		secs=$((secs - 1))
		if [ $secs -le 0 ]; then
			printf "%s\n" "${red}Error: timeout waiting pods to terminate" >&2
			exit 1
		fi
	done
	printf "\n%s\n" "${bold}Kubernetes resource status in $project namespace:${reset}"
	kubectl get all -n "$project"
}
function test_core_metadata() {
	printf "\n%s\n" "${bold}Verify core metadata...${reset}"
	local core_js namespace pod image_name signal_name comm
	core_js=$(koredumpctl list -n koredump --pod coretest -o json -1)
	if [ -z "$core_js" ]; then
		printf "%s\n" "${red}Error: missing JSON metadata for core${reset}" >&2
		exit 1
	fi
	namespace=$(echo "$core_js" | jq -r '.namespace')
	pod=$(echo "$core_js" | jq -r '.pod')
	image_name=$(echo "$core_js" | jq -r '.image_name')
	signal_name=$(echo "$core_js" | jq -r '.COREDUMP_SIGNAL_NAME')
	comm=$(echo "$core_js" | jq -r '.COREDUMP_COMM')
	if [ "$namespace" != "$project" ]; then
		printf "%s\n" "${red}Error: incorrect namespace: '${namespace}' != '${project}'${reset}" >&2
		exit 1
	fi
	if [ "$pod" != "coretest" ]; then
		printf "%s\n" "${red}Error: incorrect pod: '${pod}' != 'coretest'${reset}" >&2
		exit 1
	fi
	if [ "$image_name" != "$test_image_name" ]; then
		printf "%s\n" "${red}Error: incorrect image name: '${image_name}' != '${test_image_name}'${reset}" >&2
		exit 1
	fi
	if [ "$signal_name" != "SIGSEGV" ]; then
		printf "%s\n" "${red}Error: incorrect signal: '${signal_name}' != 'SIGSEGV'${reset}" >&2
		exit 1
	fi
	if [ "$comm" != "pycore" ]; then
		printf "%s\n" "${red}Error: incorrect COREDUMP_COMM: '${comm}' != 'pycore'${reset}" >&2
		exit 1
	fi
	printf "%s\n" "${green}Core metadata is OK.${reset}"
}
function test_core_get() {
	printf "\n%s\n" "${bold}Verify core download...${reset}"
	if test -f core.pycore.*.json; then
		rm core.pycore.*.json
	fi
	if test -f core.pycore.*; then
		rm core.pycore.*
	fi
	koredumpctl get -n koredump --pod coretest -1 || exit
	if ! test -f core.pycore.*.json; then
		printf "%s\n" "${red}Error: core JSON metadata download failed${reset}" >&2
		exit 1
	fi
	if ! jq <core.pycore.*.json >/dev/null; then
		printf "%s\n" "${red}Error: core JSON metadata parsing failed${reset}" >&2
		exit 1
	fi
	rm core.pycore.*.json
	if ! test -f core.pycore.*; then
		printf "%s\n" "${red}Error: core download failed${reset}" >&2
		exit 1
	fi
	printf "%s\n" "${green}Core download is OK.${reset}"
}

no_uninstall=""

opts=$(getopt --longoptions "help,no-uninstall" \
	--options "hU" --name "$(basename "$0")" -- "$@")
eval set -- "$opts"
while [[ $# -gt 0 ]]; do
	case "$1" in
	-U | --no-uninstall)
		no_uninstall="true"
		shift 2
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		break
		;;
	esac
done

check_core_pattern || exit
if ! type kubectl &>/dev/null; then
	printf "%s\n" "${red}Error: missing kubectl${reset}" >&2
	exit 1
fi

if type oc &>/dev/null && [ "$(oc project -q)" != "$project" ]; then
	echo "Switching to project $project"
	oc new-project "$project"
	oc project "$project" || exit
fi

delete_coretest_pod || exit
cleanup_pycores || exit

if helm -n "$project" status koredump &>/dev/null; then
	if [ "$no_uninstall" ]; then
		printf "%s\n" "${red}Error: koredump helm chart already installed${reset}" >&2
		exit 1
	fi
	printf "%s\n" "${bold}$project already installed, uninstalling...${reset}"
	helm_uninstall || exit
fi

git_branch=$(git symbolic-ref --short -q HEAD)
if [ "$git_branch" != "main" ]; then
	helm_set="--set-string image.tag=$git_branch"
fi

printf "\n%s\n" "${bold}helm install ${helm_set}${reset}"
helm -n "$project" install $helm_set --wait koredump charts/koredump/ || exit
printf "\n%s\n" "${bold}Waiting for koredump pods to start ...${reset}"
secs=300
while [ "$(kubectl get pods -n $project -l app.kubernetes.io/name=koredump -o json | jq -r '.items[].status.conditions[].status | select(.=="False")')" ]; do
	sleep 3
	secs=$((secs - 3))
	if [ $secs -le 0 ]; then
		printf "%s\n" "${red}Error: timed out waiting koredump pods to start${reset}" >&2
		exit 1
	fi
done

printf "\n%s\n" "${bold}Kubernetes resource status in $project namespace:${reset}"
kubectl get all -n "$project" || exit

print_hr
printf "%s\n" "${bold}koredumpctl status:${reset}"
koredumpctl status || exit
print_hr

printf "\n%s\n" "${bold}Run pod/coretest ...${reset}"
kubectl run coretest --image="$test_image_name" --restart=Never || exit

sleep 1
secs=300
while test -z "$(kubectl -n $project get pod/coretest -o jsonpath='{ .status.containerStatuses[0].state.terminated.exitCode }')"; do
	sleep 1
	secs=$((secs - 1))
	if [ $secs -le 0 ]; then
		printf "%s\n" "${red}Error: timed out waiting pod/coretest to finish${reset}" >&2
		exit 1
	fi
done

printf "\n%s\n" "${bold}pod/coretest finished, logs:${reset}"
kubectl logs coretest
print_hr
delete_coretest_pod || exit

secs=300
while test $(koredumpctl list -n koredump --pod coretest -o json | jq -r 'length') -lt 1; do
	sleep 1
	secs=$((secs - 1))
	if [ $secs -le 0 ]; then
		printf "%s\n" "${red}Error: timed out waiting core file to be available${reset}" >&2
		exit 1
	fi
done

printf "\n%s\n" "${bold}koredumpctl list:${reset}"
koredumpctl list || exit

test_core_metadata || exit
test_core_get || exit
cleanup_pycores

printf "\n%s\n" "${bold}koredumpctl list:${reset}"
koredumpctl list || exit

core_count=$(koredumpctl list -n koredump --pod coretest -o json | jq -r 'length')
if [ "$core_count" -gt 0 ]; then
	printf "%s\n" "${red}Error: unexpected core files in output${reset}" >&2
	exit 1
fi

if [ -z "$no_uninstall" ]; then
	helm_uninstall || exit
fi

printf "\n%s\n" "${green}SUCCESS${reset}"
