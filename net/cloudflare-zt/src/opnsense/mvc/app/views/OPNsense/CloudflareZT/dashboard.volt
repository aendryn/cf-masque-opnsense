{#
 # Copyright (C) 2024 OPNsense Contributors
 # All rights reserved.
 #
 # Redistribution and use in source and binary forms, with or without
 # modification, are permitted provided that the following conditions are met:
 #
 # 1. Redistributions of source code must retain the above copyright notice,
 #    this list of conditions and the following disclaimer.
 #
 # 2. Redistributions in binary form must reproduce the above copyright
 #    notice, this list of conditions and the following disclaimer in the
 #    documentation and/or other materials provided with the distribution.
 #
 # THIS SOFTWARE IS PROVIDED "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
 # INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
 # AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 # AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
 # OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 # SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 # INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 # CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 # ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 # POSSIBILITY OF SUCH DAMAGE.
#}

<script>
$(document).ready(function () {

    function statusBadge(status) {
        var map = {
            'connected':    '<span class="label label-success">{{ lang._('Connected') }}</span>',
            'connecting':   '<span class="label label-warning">{{ lang._('Connecting') }}</span>',
            'stopped':      '<span class="label label-default">{{ lang._('Stopped') }}</span>',
            'error':        '<span class="label label-danger">{{ lang._('Error') }}</span>',
            'disabled':     '<span class="label label-default">{{ lang._('Disabled') }}</span>',
        };
        return map[status] || '<span class="label label-info">' + status + '</span>';
    }

    function refreshStatus() {
        ajaxGet('/api/cloudflarezt/status/all', {}, function (data) {
            updateServiceStatusUI(data.overall || 'unknown');

            var $tbody = $('#connection-status-table tbody').empty();
            if (data.connections) {
                $.each(data.connections, function (uuid, conn) {
                    var row = $('<tr>').append(
                        $('<td>').text(conn.name || uuid),
                        $('<td>').text(conn.protocol || '—'),
                        $('<td>').html(statusBadge(conn.status)),
                        $('<td>').text(conn.client_ipv4 || '—'),
                        $('<td>').text(conn.uptime || '—'),
                        $('<td>').html(
                            '<button class="btn btn-xs btn-default btn-stop" data-uuid="' + uuid + '" title="{{ lang._('Stop') }}"><span class="fa fa-stop"></span></button> ' +
                            '<button class="btn btn-xs btn-default btn-start" data-uuid="' + uuid + '" title="{{ lang._('Start') }}"><span class="fa fa-play"></span></button>'
                        )
                    );
                    $tbody.append(row);
                });
            }
            if ($tbody.children().length === 0) {
                $tbody.append('<tr><td colspan="6" class="text-center text-muted">{{ lang._('No connections configured') }}</td></tr>');
            }
        });
    }

    // Start/stop individual connection buttons
    $(document).on('click', '.btn-start', function () {
        var uuid = $(this).data('uuid');
        ajaxCall('/api/cloudflarezt/service/startconn/' + uuid, {}, function () { refreshStatus(); });
    });
    $(document).on('click', '.btn-stop', function () {
        var uuid = $(this).data('uuid');
        ajaxCall('/api/cloudflarezt/service/stopconn/' + uuid, {}, function () { refreshStatus(); });
    });

    // Global start/stop/restart
    $('#btn-start-all').click(function () {
        ajaxCall('/api/cloudflarezt/service/start', {}, function () { setTimeout(refreshStatus, 1500); });
    });
    $('#btn-stop-all').click(function () {
        ajaxCall('/api/cloudflarezt/service/stop', {}, function () { setTimeout(refreshStatus, 1500); });
    });
    $('#btn-restart-all').click(function () {
        ajaxCall('/api/cloudflarezt/service/restart', {}, function () { setTimeout(refreshStatus, 2000); });
    });

    refreshStatus();
    setInterval(refreshStatus, 10000);
});
</script>

<div class="content-box">
    <div class="content-box-head">
        <h3>{{ lang._('Cloudflare Zero Trust — Dashboard') }}</h3>
    </div>
    <div class="content-box-main">
        <div class="row">
            <div class="col-xs-12">
                <div id="service-status-container" style="margin-bottom:10px;">
                    <span id="service-status-message"></span>
                </div>
                <div class="btn-group" style="margin-bottom:15px;">
                    <button id="btn-start-all" class="btn btn-sm btn-primary"><span class="fa fa-play"></span> {{ lang._('Start All') }}</button>
                    <button id="btn-stop-all" class="btn btn-sm btn-default"><span class="fa fa-stop"></span> {{ lang._('Stop All') }}</button>
                    <button id="btn-restart-all" class="btn btn-sm btn-default"><span class="fa fa-refresh"></span> {{ lang._('Restart All') }}</button>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-xs-12">
                <table id="connection-status-table" class="table table-condensed table-striped table-hover">
                    <thead>
                        <tr>
                            <th>{{ lang._('Connection') }}</th>
                            <th>{{ lang._('Protocol') }}</th>
                            <th>{{ lang._('Status') }}</th>
                            <th>{{ lang._('Client IP') }}</th>
                            <th>{{ lang._('Uptime') }}</th>
                            <th>{{ lang._('Actions') }}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="6" class="text-center"><span class="fa fa-spinner fa-pulse"></span> {{ lang._('Loading...') }}</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
