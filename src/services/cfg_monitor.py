#! /usr/bin/env python3

#
# Build time tool creates static config for all actions
# based on YANG schema for attributes that are tagged with 'configure true'.
# The values are picked from defaults provided in the schema
# The configurable entities with no default fails the build.
#
# There is a global config too, that can impact all actions.
# The LOM Service comes with a pre-built config as provided at build time.
#
# Both actions & global config can be tweaked by network admin/user.
#
# This service monitors the user changes and applies to static config
# and provide it as running config. 
#
# All other services only use running config.
#
# During runtime if user updates any, this service updates the running
# config and send SIGHUP to all services. The services are required to
# reload the updated config for use.
#
# NOTE: When LoM service starts for the first time, there will not be any
# running config. All services that need running config need to sleep
# with poll to block till this service writes the file.
# Hence this service does not raise SIGHUP for first write/create.
#
# Paths to static & running file are obtained from global.rc.json
#
# Config tweaks are taken from helpers API which is implemented by
# vendor based library. Header: common/helpers.h
#
# int LoM_Get_Actions_config_tweaks(const char *buf, int bufsz);
# int LoM_Actions_config_update(const char *buf, int bufsz);
=
