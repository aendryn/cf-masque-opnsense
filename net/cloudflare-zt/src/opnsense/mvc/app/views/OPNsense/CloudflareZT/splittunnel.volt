{#
 # Copyright (C) 2024 OPNsense Contributors
 # All rights reserved.
#}

<script>
$(document).ready(function () {

    // Load connection list for the "Connection" column filter
    function loadConnectionFilter() {
        ajaxGet('/api/cloudflarezt/connection/search', {}, function (data) {
            var $sel = $('#filter-connection').empty().append('<option value="">{{ lang._('All Connections') }}</option>');
            if (data.rows) {
                $.each(data.rows, function (_, row) {
                    $sel.append($('<option>').val(row.uuid).text(row.name));
                });
            }
        });
    }

    $('#grid-split-tunnel').UIBootgrid({
        search:  '/api/cloudflarezt/splittunnel/search',
        get:     '/api/cloudflarezt/splittunnel/get/',
        set:     '/api/cloudflarezt/splittunnel/set/',
        add:     '/api/cloudflarezt/splittunnel/add/',
        del:     '/api/cloudflarezt/splittunnel/del/',
        toggle:  '/api/cloudflarezt/splittunnel/toggle/'
    });

    loadConnectionFilter();
});
</script>

<div class="content-box">
    <div class="content-box-head"><h3>{{ lang._('Split Tunnel Rules') }}</h3></div>
    <div class="content-box-main">
        <p class="text-muted">
            {{ lang._('Define which traffic is routed through (or bypassed from) each Cloudflare Zero Trust connection. In Split Tunnel mode, only explicitly included prefixes go through the tunnel. In Full Tunnel mode, all traffic goes through unless explicitly excluded.') }}
        </p>
        <table id="grid-split-tunnel"
               class="table table-condensed table-hover table-striped table-responsive"
               data-editDialog="dialogSplitTunnelRule">
            <thead>
                <tr>
                    <th data-column-id="enabled" data-type="string" data-formatter="rowtoggle">{{ lang._('Enabled') }}</th>
                    <th data-column-id="connection_ref" data-type="string" data-visible="true">{{ lang._('Connection') }}</th>
                    <th data-column-id="action" data-type="string" data-visible="true">{{ lang._('Action') }}</th>
                    <th data-column-id="type" data-type="string" data-visible="true">{{ lang._('Type') }}</th>
                    <th data-column-id="value" data-type="string" data-visible="true">{{ lang._('Value') }}</th>
                    <th data-column-id="description" data-type="string" data-visible="true">{{ lang._('Description') }}</th>
                    <th data-column-id="commands" data-width="130" data-formatter="commands" data-sortable="false" data-visible="true">{{ lang._('Commands') }}</th>
                    <th data-column-id="uuid" data-type="string" data-identifier="true" data-visible="false">{{ lang._('ID') }}</th>
                </tr>
            </thead>
            <tbody></tbody>
            <tfoot>
                <tr>
                    <td colspan="7">
                        <button data-action="add" type="button" class="btn btn-xs btn-default"><span class="fa fa-plus"></span></button>
                        <button data-action="deleteSelected" type="button" class="btn btn-xs btn-default"><span class="fa fa-trash-o"></span></button>
                    </td>
                </tr>
            </tfoot>
        </table>
        <div id="cfztSplitChangeMessage" class="alert alert-info" style="display:none;">
            {{ lang._('Changes require a service restart to take effect.') }}
            <button class="btn btn-primary btn-sm" onclick="ajaxCall('/api/cloudflarezt/service/reconfigure',{},function(){$('#cfztSplitChangeMessage').hide();});">
                {{ lang._('Apply Changes') }}
            </button>
        </div>
    </div>
</div>

{{ partial("layout_partials/base_dialog", ['fields': ruleForm, 'id': 'dialogSplitTunnelRule', 'label': lang._('Edit Split Tunnel Rule')]) }}
