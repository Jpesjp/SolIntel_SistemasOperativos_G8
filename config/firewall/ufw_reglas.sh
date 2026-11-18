#!/usr/bin/env bash
# Reglas de firewall (UFW, Ubuntu): todo lo entrante cerrado excepto SSH y la web de SolIntel.
set -e
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH administracion'
ufw allow 8080/tcp comment 'SolIntel web'
ufw limit 22/tcp
ufw logging on
ufw --force enable
ufw status verbose
