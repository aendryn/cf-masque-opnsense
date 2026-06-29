{#
 # Copyright (C) 2024 OPNsense Contributors
 # All rights reserved.
#}

<script>
$(document).ready(function () {
    var refreshTimer = null;

    function formatUptime(val) {
        return val || '{{ lang._('unknown') }}';
    }

    function statusBadge(status) {
        var cls = {
            'connected': 'success',
            'stopped': 'default',
            'disabled': 'warning',
        }[status] || 'default';
        return '<span class="label label-' + cls + '">' + status + '</span>';
    }

    function loadStatus() {
        ajaxGet('/api/cloudflarezt/service/allstatus', {}, function (data) {
            var $tbody = $('#status-table tbody').empty();
            if (!data || !data.connections) {
                $tbody.append('<tr><td colspan="5">{{ lang._('No connections configured.') }}</td></tr>');
                return;
            }
            var overall = data.overall || 'unknown';
            $('#overall-status').html(statusBadge(overall));

            $.each(data.connections, function (uuid, conn) {
                var pid = conn.pid ? conn.pid : '—';
                var uptime = conn.uptime ? conn.uptime : '—';
                var ip = conn.client_ipv4 || '—';
                $tbody.append(
                    '<tr>' +
                    '<td>' + escapeHtml(conn.name) + '</td>' +
                    '<td>' + escapeHtml(conn.protocol) + '</td>' +
                    '<td>' + statusBadge(conn.status) + '</td>' +
                    '<td>' + escapeHtml(ip) + '</td>' +
                    '<td>' + escapeHtml(String(uptime)) + '</td>' +
                    '<td><button class="btn btn-xs btn-primary btn-start-conn" data-uuid="' + uuid + '"><span class="fa fa-play"></span></button>' +
                    ' <button class="btn btn-xs btn-danger btn-stop-conn" data-uuid="' + uuid + '"><span class="fa fa-stop"></span></button></td>' +
                    '</tr>'
                );
            });
        });
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
        });
    }

    $(document).on('click', '.btn-start-conn', function () {
        var uuid = $(this).data('uuid');
        ajaxCall('/api/cloudflarezt/service/startconn/' + uuid, {}, function () { loadStatus(); });
    });

    $(document).on('click', '.btn-stop-conn', function () {
        var uuid = $(this).data('uuid');
        ajaxCall('/api/cloudflarezt/service/stopconn/' + uuid, {}, function () { loadStatus(); });
    });

    $('#btn-refresh').click(function () { loadStatus(); });

    $('#auto-refresh').change(function () {
        if ($(this).is(':checked')) {
            refreshTimer = setInterval(loadStatus, 10000);
        } else {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
    });

    loadStatus();
});
</script>

<div class="content-box">
    <div class="content-box-head">
        <h3>{{ lang._('Connection Status') }}
            <span id="overall-status" style="margin-left:10px;"></span>
        </h3>
    </div>
    <div class="content-box-main">
        <div style="margin-bottom:10px;">
            <button id="btn-refresh" class="btn btn-default btn-sm">
                <span class="fa fa-refresh"></span> {{ lang._('Refresh') }}
            </button>
            <label style="margin-left:15px;font-weight:normal;">
                <input type="checkbox" id="auto-refresh"> {{ lang._('Auto-refresh every 10s') }}
            </label>
        </div>
        <table id="status-table" class="table table-striped table-condensed">
            <thead>
                <tr>
                    <th>{{ lang._('Name') }}</th>
                    <th>{{ lang._('Protocol') }}</th>
                    <th>{{ lang._('Status') }}</th>
                    <th>{{ lang._('Client IP') }}</th>
                    <th>{{ lang._('Uptime') }}</th>
                    <th>{{ lang._('Actions') }}</th>
                </tr>
            </thead>
            <tbody>
                <tr><td colspan="6"><em>{{ lang._('Loading...') }}</em></td></tr>
            </tbody>
        </table>
    </div>
</div>
