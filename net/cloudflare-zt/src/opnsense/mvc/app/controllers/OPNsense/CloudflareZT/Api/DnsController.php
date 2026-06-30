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

class DnsController extends ApiControllerBase
{
    public function getAction()
    {
        $model = new CloudflareZT();
        return [
            'dns' => [
                'dns_mode'       => (string)$model->dns->dns_mode,
                'custom_servers' => (string)$model->dns->custom_servers,
                'search_domains' => (string)$model->dns->search_domains,
            ]
        ];
    }

    public function setAction()
    {
        if (!$this->request->isPost()) {
            return ['result' => 'failed', 'message' => 'POST required'];
        }

        $model = new CloudflareZT();
        $body  = $this->request->getPost('dns');

        $allowed_modes = ['system', 'cloudflare_gateway', 'custom'];
        if (!empty($body['dns_mode']) && in_array($body['dns_mode'], $allowed_modes, true)) {
            $model->dns->dns_mode = $body['dns_mode'];
        }

        if (isset($body['custom_servers'])) {
            $model->dns->custom_servers = preg_replace('/[\r\n\t]/', '', $body['custom_servers']);
        }
        if (isset($body['search_domains'])) {
            $model->dns->search_domains = preg_replace('/[\r\n\t]/', '', $body['search_domains']);
        }

        $validation = $model->performValidation();
        if ($validation->count() > 0) {
            $errors = [];
            foreach ($validation as $msg) {
                $errors[] = $msg->getMessage();
            }
            return ['result' => 'failed', 'validations' => $errors];
        }

        $model->serializeToConfig();
        \OPNsense\Core\Config::getInstance()->save();

        $backend = new Backend();
        $backend->configdRun('cloudflarezt applydns');

        return ['result' => 'saved'];
    }
}
