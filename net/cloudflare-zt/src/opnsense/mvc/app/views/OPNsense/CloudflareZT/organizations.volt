{#
 # Copyright (C) 2024 OPNsense Contributors
 # All rights reserved.
#}

<script>
$(document).ready(function () {
    $('#grid-organizations').UIBootgrid({
        search:  '/api/cloudflarezt/organization/search',
        get:     '/api/cloudflarezt/organization/get/',
        set:     '/api/cloudflarezt/organization/set/',
        add:     '/api/cloudflarezt/organization/add/',
        del:     '/api/cloudflarezt/organization/del/',
        toggle:  '/api/cloudflarezt/organization/toggle/'
    });

    $(document).on('click', '.btn-validatetoken', function (e) {
        e.stopPropagation();
        var uuid = $(this).data('uuid');
        ajaxCall('/api/cloudflarezt/organization/validatetoken/' + uuid, {}, function (data) {
            if (data.result === 'valid') {
                BootstrapDialog.alert('<span class="text-success"><span class="fa fa-check"></span> {{ lang._('API token is valid') }}</span>');
            } else {
                BootstrapDialog.alert('<span class="text-danger"><span class="fa fa-times"></span> {{ lang._('Invalid token') }}: ' + (data.message || '') + '</span>');
            }
        });
    });
});
</script>

<div class="content-box">
    <div class="content-box-head"><h3>{{ lang._('Cloudflare Organizations') }}</h3></div>
    <div class="content-box-main">
        <table id="grid-organizations"
               class="table table-condensed table-hover table-striped table-responsive"
               data-editDialog="dialogOrganization">
            <thead>
                <tr>
                    <th data-column-id="enabled" data-type="string" data-formatter="rowtoggle">{{ lang._('Enabled') }}</th>
                    <th data-column-id="name" data-type="string" data-visible="true">{{ lang._('Name') }}</th>
                    <th data-column-id="account_id" data-type="string" data-visible="true">{{ lang._('Account ID') }}</th>
                    <th data-column-id="team_name" data-type="string" data-visible="true">{{ lang._('Team Name') }}</th>
                    <th data-column-id="description" data-type="string" data-visible="true">{{ lang._('Description') }}</th>
                    <th data-column-id="commands" data-width="130" data-formatter="commands" data-sortable="false" data-visible="true">{{ lang._('Commands') }}</th>
                    <th data-column-id="uuid" data-type="string" data-identifier="true" data-visible="false">{{ lang._('ID') }}</th>
                </tr>
            </thead>
            <tbody></tbody>
            <tfoot>
                <tr>
                    <td colspan="6">
                        <button data-action="add" type="button" class="btn btn-xs btn-default"><span class="fa fa-plus"></span></button>
                        <button data-action="deleteSelected" type="button" class="btn btn-xs btn-default"><span class="fa fa-trash-o"></span></button>
                    </td>
                </tr>
            </tfoot>
        </table>
    </div>
</div>

{{ partial("layout_partials/base_dialog", ['fields': organizationForm, 'id': 'dialogOrganization', 'label': lang._('Edit Organization')]) }}
