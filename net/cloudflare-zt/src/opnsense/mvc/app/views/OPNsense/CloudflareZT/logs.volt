{#
 # Copyright (C) 2024 OPNsense Contributors
 # All rights reserved.
#}

<script>
$(document).ready(function () {

    function loadConnections() {
        ajaxGet('/api/cloudflarezt/connection/search', {}, function (data) {
            var $sel = $('#log-connection-select').empty().append('<option value="all">{{ lang._('All Connections') }}</option>');
            if (data.rows) {
                $.each(data.rows, function (_, row) {
                    $sel.append($('<option>').val(row.uuid).text(row.name));
                });
            }
        });
    }

    function fetchLogs() {
        var uuid = $('#log-connection-select').val();
        var lines = $('#log-lines-select').val();
        var $out = $('#log-output').html('<span class="fa fa-spinner fa-pulse"></span>');

        var url = '/api/cloudflarezt/diagnostics/logs/' + uuid + '?lines=' + lines;
        ajaxGet(url, {}, function (data) {
            $out.empty();
            var text = '';
            if (data.log) {
                text = data.log;
            } else if (Array.isArray(data.entries)) {
                text = data.entries.join('\n');
            } else {
                text = JSON.stringify(data, null, 2);
            }
            $out.append($('<pre>').addClass('log-pre').text(text));
            $out.scrollTop($out[0].scrollHeight);
        });
    }

    $('#btn-fetch-logs').click(fetchLogs);
    $('#btn-clear-log-output').click(function () { $('#log-output').empty(); });

    var autoRefreshTimer = null;
    $('#chk-auto-refresh').change(function () {
        if ($(this).is(':checked')) {
            autoRefreshTimer = setInterval(fetchLogs, 5000);
        } else {
            clearInterval(autoRefreshTimer);
        }
    });

    loadConnections();
    fetchLogs();
});
</script>

<style>
.log-pre { max-height: 600px; overflow-y: auto; font-size: 11px; }
</style>

<div class="content-box">
    <div class="content-box-head"><h3>{{ lang._('Logs') }}</h3></div>
    <div class="content-box-main">
        <div class="row" style="margin-bottom:10px;">
            <div class="col-sm-3">
                <select id="log-connection-select" class="selectpicker" data-width="100%"></select>
            </div>
            <div class="col-sm-2">
                <select id="log-lines-select" class="selectpicker" data-width="100%">
                    <option value="50">50 {{ lang._('lines') }}</option>
                    <option value="100" selected>100 {{ lang._('lines') }}</option>
                    <option value="500">500 {{ lang._('lines') }}</option>
                    <option value="2000">2000 {{ lang._('lines') }}</option>
                </select>
            </div>
            <div class="col-sm-7">
                <button id="btn-fetch-logs" class="btn btn-primary btn-sm"><span class="fa fa-refresh"></span> {{ lang._('Fetch') }}</button>
                <button id="btn-clear-log-output" class="btn btn-default btn-sm"><span class="fa fa-eraser"></span> {{ lang._('Clear') }}</button>
                <label class="checkbox-inline" style="margin-left:10px;">
                    <input type="checkbox" id="chk-auto-refresh"> {{ lang._('Auto-refresh (5s)') }}
                </label>
            </div>
        </div>
        <div id="log-output" class="panel panel-default" style="padding:10px;min-height:100px;">
            <span class="fa fa-spinner fa-pulse"></span>
        </div>
    </div>
</div>
