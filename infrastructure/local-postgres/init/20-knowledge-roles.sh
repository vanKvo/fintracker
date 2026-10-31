#!/bin/sh
# Creates Knowledge's login roles on the first start of the volume. The script itself lives in the Knowledge repo
# and is mounted at /opt/fintracker/knowledge-roles.sh (see docker-compose.yml).
set -eu

sh /opt/fintracker/knowledge-roles.sh
