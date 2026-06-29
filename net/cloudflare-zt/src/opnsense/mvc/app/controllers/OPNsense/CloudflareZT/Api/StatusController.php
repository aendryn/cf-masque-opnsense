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

class StatusController extends ApiControllerBase
{
    // Overall status of all connections
    public function allAction()
    {
        $backend = new Backend();
        $rawResult = trim($backend->configdRun('cloudflarezt allstatus'));

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['connections' => [], 'error' => $rawResult];
        }
        return $result;
    }

    // Status for a specific connection
    public function connectionAction($uuid = null)
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

    // Traffic statistics for a connection
    public function statsAction($uuid = null)
    {
        if (empty($uuid)) {
            return ['result' => 'failed', 'message' => 'UUID required'];
        }
        if (!preg_match('/^[a-f0-9\-]{36}$/', $uuid)) {
            return ['result' => 'failed', 'message' => 'Invalid UUID'];
        }

        $backend = new Backend();
        $rawResult = trim($backend->configdRun("cloudflarezt stats {$uuid}"));

        $result = json_decode($rawResult, true);
        if ($result === null) {
            return ['result' => 'error', 'message' => $rawResult];
        }
        return $result;
    }
}
