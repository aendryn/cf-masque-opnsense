{#
 # Copyright (C) 2024 OPNsense Contributors
 # All rights reserved.
 # (license header omitted for brevity — same BSD 2-clause as other files)
#}

<script>
$(document).ready(function () {

    $('#grid-connections').UIBootgrid({
        search:  '/api/cloudflarezt/connection/search',
        get:     '/api/cloudflarezt/connection/get/',
        set:     '/api/cloudflarezt/connection/set/',
        add:     '/api/cloudflarezt/connection/add/',
        del:     '/api/cloudflarezt/connection/del/',
        toggle:  '/api/cloudflarezt/connection/toggle/'
    });

    // Register / Enroll buttons in the action column
    $(document).on('click', '.btn-register', function (e) {
        e.stopPropagation();
        var uuid = $(this).data('uuid');
        BootstrapDialog.confirm({
            title: '{{ lang._('Register Device') }}',
            message: '{{ lang._('This will register a new WARP device with Cloudflare. Continue?') }}',
            callback: function (ok) {
                if (!ok) return;
                ajaxCall('/api/cloudflarezt/connection/register/' + uuid, {}, function (data) {
                    if (data.result === 'ok' || data.result === 'registered') {
                        BootstrapDialog.alert('{{ lang._('Device registered successfully') }}');
                        $('#grid-connections').bootgrid('reload');
                    } else {
                        BootstrapDialog.alert('{{ lang._('Registration failed') }}: ' + (data.message || JSON.stringify(data)));
                    }
                });
            }
        });
    });

    $(document).on('click', '.btn-enroll', function (e) {
        e.stopPropagation();
        var uuid = $(this).data('uuid');
        ajaxCall('/api/cloudflarezt/connection/enroll/' + uuid, {}, function (data) {
            if (data.result === 'ok' || data.result === 'enrolled') {
                BootstrapDialog.alert('{{ lang._('MASQUE key enrolled successfully') }}');
                $('#grid-connections').bootgrid('reload');
            } else {
                BootstrapDialog.alert('{{ lang._('Enrollment failed') }}: ' + (data.message || JSON.stringify(data)));
            }
        });
    });

    $(document).on('click', '.btn-rotatekey', function (e) {
        e.stopPropagation();
        var uuid = $(this).data('uuid');
        BootstrapDialog.confirm({
            title: '{{ lang._('Rotate Key') }}',
            message: '{{ lang._('Generate a new MASQUE key and re-enroll with Cloudflare. The connection will briefly disconnect. Continue?') }}',
            callback: function (ok) {
                if (!ok) return;
                ajaxCall('/api/cloudflarezt/key/rotate/' + uuid, {}, function (data) {
                    if (data.result === 'ok') {
                        BootstrapDialog.alert('{{ lang._('Key rotated successfully') }}');
                    } else {
                        BootstrapDialog.alert('{{ lang._('Key rotation failed') }}: ' + (data.message || JSON.stringify(data)));
                    }
                });
            }
        });
    });
});
</script>

<ul class="nav nav-tabs" data-tabs="tabs" id="maintabs">
    <li class="active"><a data-toggle="tab" href="#tab-connections">{{ lang._('Connections') }}</a></li>
</ul>

<div class="tab-content content-box tab-content">
    <div id="tab-connections" class="tab-pane fade in active">
        <table id="grid-connections"
               class="table table-condensed table-hover table-striped table-responsive"
               data-editDialog="dialogConnection"
               data-editAlert="cfztChangeMessage">
            <thead>
                <tr>
                    <th data-column-id="enabled" data-type="string" data-formatter="rowtoggle">{{ lang._('Enabled') }}</th>
                    <th data-column-id="name" data-type="string" data-visible="true">{{ lang._('Name') }}</th>
                    <th data-column-id="protocol" data-type="string" data-visible="true">{{ lang._('Protocol') }}</th>
                    <th data-column-id="registration_status" data-type="string" data-visible="true">{{ lang._('Status') }}</th>
                    <th data-column-id="client_ipv4" data-type="string" data-visible="true">{{ lang._('Client IP') }}</th>
                    <th data-column-id="description" data-type="string" data-visible="true">{{ lang._('Description') }}</th>
                    <th data-column-id="commands" data-width="220" data-formatter="commands" data-sortable="false" data-visible="true">{{ lang._('Commands') }}</th>
                    <th data-column-id="uuid" data-type="string" data-identifier="true" data-visible="false">{{ lang._('ID') }}</th>
                </tr>
            </thead>
            <tbody>
            </tbody>
            <tfoot>
                <tr>
                    <td colspan="7">
                        <button data-action="add" type="button" class="btn btn-xs btn-default"><span class="fa fa-plus"></span></button>
                        <button data-action="deleteSelected" type="button" class="btn btn-xs btn-default"><span class="fa fa-trash-o"></span></button>
                    </td>
                </tr>
            </tfoot>
        </table>
        <div id="cfztChangeMessage" class="alert alert-info" style="display:none;">
            {{ lang._('Changes require a service restart to take effect.') }}
            <button class="btn btn-primary btn-sm" onclick="ajaxCall('/api/cloudflarezt/service/reconfigure',{},function(){$('#cfztChangeMessage').hide();});">
                {{ lang._('Apply Changes') }}
            </button>
        </div>
    </div>
</div>

{{ partial("layout_partials/base_dialog", ['fields': connectionForm, 'id': 'dialogConnection', 'label': lang._('Edit Connection')]) }}
