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

class DiagnosticsController extends ApiControllerBase
{
    // Full diagnostics for a connection (ping, route check, interface stats)
    public function runAction($uuid = null)
    {
        if (!$this->request->isPost() || empty($uuid)) {
            return ['result' => 'failed', 'message' => 'POST with UUID required'];
        }
        if (!preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
            return ['result' => 'failed', 'message' => 'Invalid UUID'];
        }

        $backend = new Backend();
        $rawResult = trim($backend->configdRun("cloudflarezt diagnostics {$uuid}"));

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['result' => 'error', 'message' => $rawResult];
        }
        return $result;
    }

    // Fetch recent log entries for a connection (or all connections)
    public function logsAction($uuid = null)
    {
        $lines = (int)$this->request->getQuery('lines', null, 100);
        $lines = max(10, min(5000, $lines));

        $backend = new Backend();
        if (!empty($uuid)) {
            if (!preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
                return ['result' => 'failed', 'message' => 'Invalid UUID'];
            }
            $rawResult = trim($backend->configdRun("cloudflarezt logs {$uuid} {$lines}"));
        } else {
            $rawResult = trim($backend->configdRun("cloudflarezt logs all {$lines}"));
        }

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['log' => $rawResult, 'result' => 'ok'];
        }
        return $result;
    }

    // Ping Cloudflare endpoints to check connectivity
    public function pingAction()
    {
        if (!$this->request->isPost()) {
            return ['result' => 'failed', 'message' => 'POST required'];
        }

        $backend = new Backend();
        $rawResult = trim($backend->configdRun('cloudflarezt ping'));

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['result' => 'error', 'message' => $rawResult];
        }
        return $result;
    }
}
