{#
 # Copyright (C) 2024 OPNsense Contributors
 # All rights reserved.
#}

<script>
$(document).ready(function () {
    var currentStep = 1;
    var wizardData = {};

    function showStep(n) {
        $('.wizard-step').hide();
        $('#wizard-step-' + n).show();
        $('#wizard-step-indicator').text('{{ lang._('Step') }} ' + n + ' / 4');
        currentStep = n;
    }

    // Step 1: Select/create organization
    $('#wizard-next-1').click(function () {
        var mode = $('input[name=wizard-org-mode]:checked').val();
        if (mode === 'new') {
            wizardData.org_name    = $('#wizard-org-name').val().trim();
            wizardData.org_acctid  = $('#wizard-org-acctid').val().trim();
            wizardData.org_token   = $('#wizard-org-token').val().trim();
            wizardData.org_team    = $('#wizard-org-team').val().trim();
            if (!wizardData.org_name || !wizardData.org_acctid || !wizardData.org_token) {
                BootstrapDialog.alert('{{ lang._('Name, Account ID, and API Token are required') }}');
                return;
            }
        } else {
            wizardData.org_uuid = $('#wizard-org-existing').val();
            if (!wizardData.org_uuid) {
                BootstrapDialog.alert('{{ lang._('Please select an organization') }}');
                return;
            }
        }
        showStep(2);
    });

    // Step 2: Connection settings
    $('#wizard-next-2').click(function () {
        wizardData.conn_name     = $('#wizard-conn-name').val().trim();
        wizardData.conn_protocol = $('#wizard-conn-protocol').val();
        wizardData.conn_mode     = $('#wizard-conn-mode').val();
        wizardData.conn_device   = $('#wizard-conn-device').val().trim();
        if (!wizardData.conn_name) {
            BootstrapDialog.alert('{{ lang._('Connection name is required') }}');
            return;
        }
        showStep(3);
    });

    // Step 3: Register device
    $('#wizard-btn-register').click(function () {
        $('#wizard-register-output').html('<span class="fa fa-spinner fa-pulse"></span> {{ lang._('Registering...') }}');
        ajaxCall('/api/cloudflarezt/wizard/register', wizardData, function (data) {
            if (data.result === 'ok') {
                wizardData.conn_uuid = data.uuid;
                $('#wizard-register-output').html('<span class="text-success fa fa-check"></span> ' +
                    '{{ lang._('Registered as') }}: ' + (data.client_ipv4 || '') + ' ' + (data.client_ipv6 || ''));
                $('#wizard-next-3').prop('disabled', false);
            } else {
                $('#wizard-register-output').html('<span class="text-danger fa fa-times"></span> ' + (data.message || JSON.stringify(data)));
            }
        });
    });

    $('#wizard-next-3').click(function () { showStep(4); });

    // Step 4: Review and apply
    $('#wizard-btn-apply').click(function () {
        ajaxCall('/api/cloudflarezt/service/reconfigure', {}, function (data) {
            $('#wizard-apply-output').html('<span class="text-success fa fa-check"></span> {{ lang._('Configuration applied. Connection starting...') }}');
            setTimeout(function () { window.location.href = '/ui/cloudflarezt'; }, 2000);
        });
    });

    // Load existing orgs for the dropdown
    ajaxGet('/api/cloudflarezt/organization/search', {}, function (data) {
        var $sel = $('#wizard-org-existing').empty();
        if (data.rows && data.rows.length) {
            $.each(data.rows, function (_, row) {
                $sel.append($('<option>').val(row.uuid).text(row.name));
            });
        } else {
            $('input[name=wizard-org-mode][value=new]').prop('checked', true).trigger('change');
            $('input[name=wizard-org-mode][value=existing]').prop('disabled', true);
        }
    });

    $('input[name=wizard-org-mode]').change(function () {
        var mode = $(this).val();
        $('#wizard-new-org-fields').toggle(mode === 'new');
        $('#wizard-existing-org-fields').toggle(mode === 'existing');
    }).filter(':checked').trigger('change');

    showStep(1);
});
</script>

<div class="content-box">
    <div class="content-box-head">
        <h3>{{ lang._('Cloudflare Zero Trust Setup Wizard') }}
            <small id="wizard-step-indicator" style="margin-left:10px;"></small>
        </h3>
    </div>
    <div class="content-box-main">

        <!-- Step 1: Organization -->
        <div class="wizard-step" id="wizard-step-1">
            <h4>{{ lang._('Step 1: Cloudflare Organization') }}</h4>
            <div class="form-group">
                <label><input type="radio" name="wizard-org-mode" value="existing" checked> {{ lang._('Use existing organization') }}</label><br>
                <label><input type="radio" name="wizard-org-mode" value="new"> {{ lang._('Add new organization') }}</label>
            </div>
            <div id="wizard-existing-org-fields">
                <div class="form-group">
                    <label>{{ lang._('Organization') }}</label>
                    <select id="wizard-org-existing" class="selectpicker form-control"></select>
                </div>
            </div>
            <div id="wizard-new-org-fields" style="display:none;">
                <div class="form-group"><label>{{ lang._('Name') }}</label><input type="text" id="wizard-org-name" class="form-control"></div>
                <div class="form-group"><label>{{ lang._('Account ID') }}</label><input type="text" id="wizard-org-acctid" class="form-control" placeholder="32 hex characters"></div>
                <div class="form-group"><label>{{ lang._('API Token') }}</label><input type="password" id="wizard-org-token" class="form-control"></div>
                <div class="form-group"><label>{{ lang._('Team Name (optional)') }}</label><input type="text" id="wizard-org-team" class="form-control"></div>
            </div>
            <button id="wizard-next-1" class="btn btn-primary">{{ lang._('Next') }} &raquo;</button>
        </div>

        <!-- Step 2: Connection -->
        <div class="wizard-step" id="wizard-step-2" style="display:none;">
            <h4>{{ lang._('Step 2: Connection Settings') }}</h4>
            <div class="form-group"><label>{{ lang._('Connection Name') }}</label><input type="text" id="wizard-conn-name" class="form-control" placeholder="e.g. warp-main"></div>
            <div class="form-group">
                <label>{{ lang._('Protocol') }}</label>
                <select id="wizard-conn-protocol" class="selectpicker form-control">
                    <option value="warp_masque">{{ lang._('WARP — MASQUE/HTTP3 (recommended)') }}</option>
                    <option value="warp_wireguard">{{ lang._('WARP — WireGuard') }}</option>
                    <option value="cloudflared">{{ lang._('Cloudflare Tunnel') }}</option>
                </select>
            </div>
            <div class="form-group">
                <label>{{ lang._('Tunnel Mode') }}</label>
                <select id="wizard-conn-mode" class="selectpicker form-control">
                    <option value="split">{{ lang._('Split Tunnel') }}</option>
                    <option value="full">{{ lang._('Full Tunnel') }}</option>
                </select>
            </div>
            <div class="form-group"><label>{{ lang._('Device Name (optional)') }}</label><input type="text" id="wizard-conn-device" class="form-control" placeholder="OPNsense-Router"></div>
            <button id="wizard-next-2" class="btn btn-primary">{{ lang._('Next') }} &raquo;</button>
        </div>

        <!-- Step 3: Register -->
        <div class="wizard-step" id="wizard-step-3" style="display:none;">
            <h4>{{ lang._('Step 3: Register Device with Cloudflare') }}</h4>
            <p>{{ lang._('Click Register to create a new WARP device registration with Cloudflare. This will generate keys and obtain your client IP addresses.') }}</p>
            <button id="wizard-btn-register" class="btn btn-primary">{{ lang._('Register Device') }}</button>
            <div id="wizard-register-output" style="margin-top:10px;"></div>
            <hr>
            <button id="wizard-next-3" class="btn btn-success" disabled>{{ lang._('Next') }} &raquo;</button>
        </div>

        <!-- Step 4: Apply -->
        <div class="wizard-step" id="wizard-step-4" style="display:none;">
            <h4>{{ lang._('Step 4: Apply Configuration') }}</h4>
            <p>{{ lang._('Your Cloudflare Zero Trust connection is configured. Click Apply to start the service.') }}</p>
            <button id="wizard-btn-apply" class="btn btn-success btn-lg">
                <span class="fa fa-check"></span> {{ lang._('Apply and Start') }}
            </button>
            <div id="wizard-apply-output" style="margin-top:10px;"></div>
        </div>

    </div>
</div>
