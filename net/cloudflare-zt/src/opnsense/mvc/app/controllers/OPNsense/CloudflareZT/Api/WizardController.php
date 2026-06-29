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

namespace OPNsense\CloudflareZT\Api;

use OPNsense\Base\ApiControllerBase;
use OPNsense\Core\Backend;
use OPNsense\Core\Config;
use OPNsense\CloudflareZT\CloudflareZT;

/**
 * Handles the setup wizard flow: creates org + connection + registers device
 * in a single orchestrated sequence.
 */
class WizardController extends ApiControllerBase
{
    public function registerAction()
    {
        if (!$this->request->isPost()) {
            return ['result' => 'failed', 'message' => 'POST required'];
        }

        $post = $this->request->getPost();
        $model = new CloudflareZT();

        // Create or reuse organization
        $orgUUID = $post['org_uuid'] ?? null;
        if (empty($orgUUID)) {
            // Create new organization
            $orgUUID = \OPNsense\Base\UID::create();
            $org = $model->organizations->organization->Add();
            $org->enabled = '1';
            $org->name = $this->sanitize($post['org_name'] ?? '');
            $org->account_id = $this->sanitize($post['org_acctid'] ?? '');
            $org->team_name = $this->sanitize($post['org_team'] ?? '');

            // Store API token in secrets (not in config.xml)
            $apiToken = $post['org_token'] ?? '';
            if (!empty($apiToken)) {
                $backend = new Backend();
                $safeToken = base64_encode($apiToken);
                $backend->configdRun("cloudflarezt setsecret org_apitoken_{$orgUUID} {$safeToken}");
                $org->api_token_ref = "org_apitoken_{$orgUUID}";
            }
        }

        // Create new connection
        $connUUID = \OPNsense\Base\UID::create();
        $conn = $model->connections->connection->Add();
        $conn->enabled = '1';
        $conn->name = $this->sanitize($post['conn_name'] ?? 'warp-main');
        $conn->protocol = $this->sanitize($post['conn_protocol'] ?? 'warp_masque');
        $conn->tunnel_mode = $this->sanitize($post['conn_mode'] ?? 'split');
        $conn->device_name = $this->sanitize($post['conn_device'] ?? 'OPNsense-Router');
        $conn->organization_ref = $orgUUID;
        $conn->registration_status = 'unregistered';
        $conn->mtu = '1280';
        $conn->reconnect_delay = '5';
        $conn->always_reconnect = '1';
        $conn->auto_rotate_keys = '1';
        $conn->key_rotation_days = '30';

        // Enable the plugin globally
        $model->general->enabled = '1';

        // Save
        $model->serializeToConfig();
        Config::getInstance()->save();

        // Now register the device via configd
        $backend = new Backend();
        $jwt = $this->sanitize($post['jwt'] ?? '');
        $rawResult = trim($backend->configdRun("cloudflarezt register {$connUUID}"));

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['result' => 'failed', 'message' => $rawResult];
        }

        $result['uuid'] = $connUUID;
        $result['org_uuid'] = $orgUUID;
        return $result;
    }

    private function sanitize(string $value): string
    {
        return htmlspecialchars(strip_tags(trim($value)), ENT_QUOTES, 'UTF-8');
    }
}
