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
use OPNsense\CloudflareZT\CloudflareZT;

class ServiceController extends ApiControllerBase
{
    public function startAction()
    {
        if (!$this->request->isPost()) {
            return ['result' => 'failed', 'message' => 'POST required'];
        }
        $backend = new Backend();
        $result = trim($backend->configdRun('cloudflarezt start'));
        return ['result' => $result ?: 'ok'];
    }

    public function stopAction()
    {
        if (!$this->request->isPost()) {
            return ['result' => 'failed', 'message' => 'POST required'];
        }
        $backend = new Backend();
        $result = trim($backend->configdRun('cloudflarezt stop'));
        return ['result' => $result ?: 'ok'];
    }

    public function restartAction()
    {
        if (!$this->request->isPost()) {
            return ['result' => 'failed', 'message' => 'POST required'];
        }
        $backend = new Backend();
        $backend->configdRun('template reload OPNsense/CloudflareZT');
        $result = trim($backend->configdRun('cloudflarezt restart'));
        return ['result' => $result ?: 'ok'];
    }

    public function statusAction()
    {
        $model = new CloudflareZT();
        $enabled = (string)$model->general->enabled === '1';

        $backend = new Backend();
        $raw = trim($backend->configdRun('cloudflarezt status'));

        if (!$enabled) {
            $status = 'disabled';
        } elseif (strpos($raw, 'running') !== false) {
            $status = 'running';
        } elseif (strpos($raw, 'stopped') !== false || $raw === '') {
            $status = 'stopped';
        } else {
            $status = 'unknown';
        }

        return ['result' => $status, 'details' => $raw];
    }

    public function reconfigureAction()
    {
        if (!$this->request->isPost()) {
            return ['result' => 'failed', 'message' => 'POST required'];
        }

        $model = new CloudflareZT();
        $model->serializeToConfig();
        \OPNsense\Core\Config::getInstance()->save();

        $backend = new Backend();
        $backend->configdRun('template reload OPNsense/CloudflareZT');

        $enabled = (string)$model->general->enabled === '1';
        if ($enabled) {
            $result = trim($backend->configdRun('cloudflarezt restart'));
        } else {
            $result = trim($backend->configdRun('cloudflarezt stop'));
        }

        return ['result' => $result ?: 'ok'];
    }

    // Start/stop a single connection by UUID
    public function startconnAction($uuid = null)
    {
        if (!$this->request->isPost() || empty($uuid)) {
            return ['result' => 'failed', 'message' => 'POST with UUID required'];
        }
        if (!preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
            return ['result' => 'failed', 'message' => 'Invalid UUID'];
        }
        $backend = new Backend();
        $result = trim($backend->configdRun("cloudflarezt startconn {$uuid}"));
        return ['result' => $result ?: 'ok'];
    }

    public function stopconnAction($uuid = null)
    {
        if (!$this->request->isPost() || empty($uuid)) {
            return ['result' => 'failed', 'message' => 'POST with UUID required'];
        }
        if (!preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
            return ['result' => 'failed', 'message' => 'Invalid UUID'];
        }
        $backend = new Backend();
        $result = trim($backend->configdRun("cloudflarezt stopconn {$uuid}"));
        return ['result' => $result ?: 'ok'];
    }
}
