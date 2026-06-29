<?php

/*
 * Copyright (C) 2024 OPNsense Contributors
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES,
 * INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
 * AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 * AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
 * OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

function cloudflarezt_enabled()
{
    $model = new \OPNsense\CloudflareZT\CloudflareZT();
    return (string)$model->general->enabled === '1';
}

function cloudflarezt_services()
{
    $services = [];

    if (!cloudflarezt_enabled()) {
        return $services;
    }

    $services[] = [
        'description' => gettext('Cloudflare Zero Trust'),
        'configd' => [
            'restart' => ['cloudflarezt restart'],
            'start'   => ['cloudflarezt start'],
            'stop'    => ['cloudflarezt stop'],
        ],
        'name' => 'cloudflarezt',
        'pidfile' => '/var/run/cfzt-monitor.pid',
    ];

    return $services;
}

function cloudflarezt_devices()
{
    // Register cfzt TUN interfaces as volatile so OPNsense knows they may appear/disappear
    return [
        ['pattern' => '^cfzt', 'spoofmac' => false, 'volatile' => true],
    ];
}

function cloudflarezt_firewall($fw)
{
    // Register firewall aliases for each active connection's peer IPs
    $model = new \OPNsense\CloudflareZT\CloudflareZT();
    $aliases = [];

    foreach ($model->connections->connection->iterateItems() as $uuid => $connection) {
        if ((string)$connection->enabled !== '1') {
            continue;
        }

        $name = preg_replace('/[^a-zA-Z0-9_]/', '_', (string)$connection->name);

        // Peer endpoint alias
        $endpoint_v4 = (string)$connection->endpoint_v4;
        $endpoint_v6 = (string)$connection->endpoint_v6;
        $peers = array_filter([$endpoint_v4, $endpoint_v6]);

        if (!empty($peers)) {
            $aliases[] = [
                'name' => 'cfzt_' . $name . '_peers',
                'type' => 'host',
                'content' => implode("\n", $peers),
                'description' => sprintf('Cloudflare ZT peers for %s', (string)$connection->name),
                'proto' => '',
            ];
        }
    }

    foreach ($aliases as $alias) {
        $fw->registerAlias($alias);
    }
}

function cloudflarezt_cron()
{
    $jobs = [];

    if (!cloudflarezt_enabled()) {
        return $jobs;
    }

    // Daily key rotation check at 3am
    $jobs[] = [
        'description' => 'Cloudflare ZT key rotation check',
        'command'     => 'cloudflarezt rotatekeyscheck',
        'parameters'  => '',
        'schedule'    => ['0', '3', '*', '*', '*'],
        'backend'     => 'configd',
    ];

    return $jobs;
}

function cloudflarezt_configure()
{
    return [
        'bootup'   => ['cloudflarezt_configure_do:2'],
        'newwanip' => ['cloudflarezt_configure_do:2'],
        'vpn'      => ['cloudflarezt_configure_do:2'],
    ];
}

function cloudflarezt_configure_do($verbose = false)
{
    if (!cloudflarezt_enabled()) {
        return;
    }
    $backend = new \OPNsense\Core\Backend();
    // Restart all connections — the daemon handles rebinding to the new WAN IP
    $backend->configdRun('cloudflarezt restart');
}

function cloudflarezt_firmware_upgrade()
{
    // Stop service cleanly before firmware upgrade to avoid tunnel state corruption
    $backend = new \OPNsense\Core\Backend();
    $backend->configdRun('cloudflarezt stop');
}

function cloudflarezt_xmlrpc_sync()
{
    return [[
        'description' => gettext('Cloudflare Zero Trust'),
        'section'     => 'OPNsense.CloudflareZT',
        'id'          => 'cloudflarezt',
        'services'    => 'cloudflarezt',
    ]];
}

function cloudflarezt_syslog()
{
    return [
        'cloudflarezt' => ['facility' => ['cfzt-warp', 'cloudflared', 'cfzt-monitor']],
    ];
}
