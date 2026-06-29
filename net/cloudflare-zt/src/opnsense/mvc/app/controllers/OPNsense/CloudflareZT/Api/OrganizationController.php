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

use OPNsense\Base\ApiMutableModelControllerBase;
use OPNsense\Core\Backend;

class OrganizationController extends ApiMutableModelControllerBase
{
    protected static $internalModelName = 'organization';
    protected static $internalModelClass = '\OPNsense\CloudflareZT\CloudflareZT';

    public function searchAction()
    {
        return $this->searchBase(
            'organizations.organization',
            ['enabled', 'name', 'description', 'account_id', 'team_name']
        );
    }

    public function getAction($uuid = null)
    {
        return $this->getBase('organization', 'organizations.organization', $uuid);
    }

    public function addAction()
    {
        return $this->addBase('organization', 'organizations.organization');
    }

    public function setAction($uuid = null)
    {
        // Intercept to handle api_token separately (store in secrets, not config.xml)
        if ($this->request->isPost()) {
            $postData = $this->request->getPost('organization');
            $apiToken = isset($postData['api_token']) ? $postData['api_token'] : null;

            if (!empty($apiToken)) {
                unset($postData['api_token']);
                $_POST['organization'] = $postData;
                // Store token in secrets store via configd
                if (!empty($uuid) && preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
                    $backend = new Backend();
                    $safeToken = base64_encode($apiToken);
                    $backend->configdRun("cloudflarezt setsecret org_apitoken_{$uuid} {$safeToken}");
                }
            }
        }
        return $this->setBase('organization', 'organizations.organization', $uuid);
    }

    public function delAction($uuid = null)
    {
        if (!empty($uuid) && preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
            // Clean up secrets for this org
            $backend = new Backend();
            $backend->configdRun("cloudflarezt delsecret org_apitoken_{$uuid}");
        }
        return $this->delBase('organizations.organization', $uuid);
    }

    public function toggleAction($uuid = null, $enabled = null)
    {
        return $this->toggleBase('organizations.organization', $uuid, $enabled);
    }

    // Validate an API token against the Cloudflare API
    public function validatetokenAction($uuid = null)
    {
        if (!$this->request->isPost() || empty($uuid)) {
            return ['result' => 'failed', 'message' => 'POST with UUID required'];
        }
        if (!preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
            return ['result' => 'failed', 'message' => 'Invalid UUID'];
        }

        $backend = new Backend();
        $rawResult = trim($backend->configdRun("cloudflarezt validatetoken {$uuid}"));

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['result' => 'failed', 'message' => $rawResult];
        }
        return $result;
    }
}
