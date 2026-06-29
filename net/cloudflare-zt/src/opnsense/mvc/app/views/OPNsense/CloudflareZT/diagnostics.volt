{#
 # Copyright (C) 2024 OPNsense Contributors
 # All rights reserved.
#}

<script>
$(document).ready(function () {

    function loadConnections() {
        ajaxGet('/api/cloudflarezt/connection/search', {}, function (data) {
            var $sel = $('#diag-connection-select').empty().append('<option value="all">{{ lang._('All Connections') }}</option>');
            if (data.rows) {
                $.each(data.rows, function (_, row) {
                    $sel.append($('<option>').val(row.uuid).text(row.name));
                });
            }
        });
    }

    $('#btn-run-diagnostics').click(function () {
        var uuid = $('#diag-connection-select').val();
        var $out = $('#diagnostics-output').html('<span class="fa fa-spinner fa-pulse"></span> {{ lang._('Running diagnostics...') }}');

        var url = uuid === 'all' ? '/api/cloudflarezt/diagnostics/run/all' : '/api/cloudflarezt/diagnostics/run/' + uuid;
        ajaxCall(url, {}, function (data) {
            $out.empty();
            if (typeof data === 'object') {
                $out.append($('<pre>').text(JSON.stringify(data, null, 2)));
            } else {
                $out.text(data);
            }
        });
    });

    $('#btn-ping').click(function () {
        var $out = $('#diagnostics-output').html('<span class="fa fa-spinner fa-pulse"></span> {{ lang._('Pinging Cloudflare endpoints...') }}');
        ajaxCall('/api/cloudflarezt/diagnostics/ping', {}, function (data) {
            $out.empty().append($('<pre>').text(JSON.stringify(data, null, 2)));
        });
    });

    loadConnections();
});
</script>

<div class="content-box">
    <div class="content-box-head"><h3>{{ lang._('Diagnostics') }}</h3></div>
    <div class="content-box-main">
        <div class="row" style="margin-bottom:15px;">
            <div class="col-sm-4">
                <select id="diag-connection-select" class="selectpicker" data-width="100%">
                    <option value="all">{{ lang._('All Connections') }}</option>
                </select>
            </div>
            <div class="col-sm-8">
                <button id="btn-run-diagnostics" class="btn btn-primary btn-sm">
                    <span class="fa fa-stethoscope"></span> {{ lang._('Run Diagnostics') }}
                </button>
                <button id="btn-ping" class="btn btn-default btn-sm">
                    <span class="fa fa-bullseye"></span> {{ lang._('Ping Cloudflare Endpoints') }}
                </button>
            </div>
        </div>
        <div class="row">
            <div class="col-xs-12">
                <div id="diagnostics-output" class="panel panel-default" style="min-height:200px;padding:10px;font-family:monospace;white-space:pre-wrap;">
                    {{ lang._('Select a connection and click Run Diagnostics.') }}
                </div>
            </div>
        </div>
    </div>
</div>
