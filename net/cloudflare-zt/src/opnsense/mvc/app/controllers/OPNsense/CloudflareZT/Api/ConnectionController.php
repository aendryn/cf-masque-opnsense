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
use OPNsense\CloudflareZT\CloudflareZT;

class ConnectionController extends ApiMutableModelControllerBase
{
    protected static $internalModelName = 'connection';
    protected static $internalModelClass = '\OPNsense\CloudflareZT\CloudflareZT';

    public function searchAction()
    {
        return $this->searchBase(
            'connections.connection',
            ['enabled', 'name', 'description', 'protocol', 'registration_status', 'client_ipv4']
        );
    }

    public function getAction($uuid = null)
    {
        return $this->getBase('connection', 'connections.connection', $uuid);
    }

    public function addAction()
    {
        return $this->addBase('connection', 'connections.connection');
    }

    public function setAction($uuid = null)
    {
        return $this->setBase('connection', 'connections.connection', $uuid);
    }

    public function delAction($uuid = null)
    {
        return $this->delBase('connections.connection', $uuid);
    }

    public function toggleAction($uuid = null, $enabled = null)
    {
        return $this->toggleBase('connections.connection', $uuid, $enabled);
    }

    // Register a new WARP device for this connection
    public function registerAction($uuid = null)
    {
        if (!$this->request->isPost() || empty($uuid)) {
            return ['result' => 'failed', 'message' => 'POST with UUID required'];
        }
        if (!preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
            return ['result' => 'failed', 'message' => 'Invalid UUID'];
        }

        $jwt = $this->request->getPost('jwt', 'string', '');
        if (!empty($jwt) && !preg_match('/^[A-Za-z0-9._-]+$/', $jwt)) {
            return ['result' => 'failed', 'message' => 'Invalid JWT format'];
        }

        $backend = new Backend();
        $rawResult = trim($backend->configdRun("cloudflarezt register {$uuid} {$jwt}"));

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['result' => 'failed', 'message' => $rawResult];
        }
        return $result;
    }

    // Re-enroll MASQUE key for an existing registration
    public function enrollAction($uuid = null)
    {
        if (!$this->request->isPost() || empty($uuid)) {
            return ['result' => 'failed', 'message' => 'POST with UUID required'];
        }
        if (!preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
            return ['result' => 'failed', 'message' => 'Invalid UUID'];
        }

        $backend = new Backend();
        $rawResult = trim($backend->configdRun("cloudflarezt enroll {$uuid}"));

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['result' => 'failed', 'message' => $rawResult];
        }
        return $result;
    }

    // Live status for a single connection
    public function connstatusAction($uuid = null)
    {
        if (empty($uuid)) {
            return ['result' => 'failed', 'message' => 'UUID required'];
        }
        if (!preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
            return ['result' => 'failed', 'message' => 'Invalid UUID'];
        }

        $backend = new Backend();
        $rawResult = trim($backend->configdRun("cloudflarezt connstatus {$uuid}"));

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['result' => 'error', 'message' => $rawResult];
        }
        return $result;
    }
}
