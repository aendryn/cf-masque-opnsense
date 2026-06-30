{#
 # Copyright (C) 2024 OPNsense Contributors
 # All rights reserved.
#}

<script>
$(document).ready(function () {

    function toggleCustomServers() {
        var mode = $('#dns-mode').val();
        $('#row-custom-servers').toggle(mode === 'custom');
    }

    // Load saved settings
    ajaxGet('/api/cloudflarezt/dns/get', {}, function (data) {
        if (!data.dns) return;
        $('#dns-mode').val(data.dns.dns_mode || 'system');
        $('#dns-custom-servers').val(data.dns.custom_servers || '');
        $('#dns-search-domains').val(data.dns.search_domains || '');
        toggleCustomServers();
    });

    $('#dns-mode').on('change', toggleCustomServers);

    $('#btn-dns-save').click(function () {
        var $btn = $(this).prop('disabled', true);
        ajaxCall('/api/cloudflarezt/dns/set', {
            dns: {
                dns_mode:       $('#dns-mode').val(),
                custom_servers: $('#dns-custom-servers').val(),
                search_domains: $('#dns-search-domains').val()
            }
        }, function (data) {
            $btn.prop('disabled', false);
            if (data.result === 'saved') {
                $('#dns-save-result').removeClass('text-danger').addClass('text-success')
                    .text('{{ lang._('Settings saved') }}').show().delay(3000).fadeOut();
            } else {
                var msg = data.validations ? data.validations.join(', ') : (data.message || JSON.stringify(data));
                $('#dns-save-result').removeClass('text-success').addClass('text-danger')
                    .text(msg).show();
            }
        });
    });
});
</script>

<div class="content-box">
    <div class="content-box-head"><h3>{{ lang._('DNS Settings') }}</h3></div>
    <div class="content-box-main" style="padding: 16px;">

        <div class="alert alert-info">
            {{ lang._('DNS settings apply globally to all connections. In Full Tunnel mode, using OPNsense DNS requires that your Unbound upstream servers are reachable through the tunnel, or that you add split-tunnel exclude rules for those servers.') }}
        </div>

        <div class="form-group">
            <label for="dns-mode">{{ lang._('DNS Mode') }}</label>
            <select id="dns-mode" class="selectpicker form-control" style="max-width: 400px;">
                <option value="system">{{ lang._('OPNsense DNS — use Unbound as configured (no override)') }}</option>
                <option value="cloudflare_gateway">{{ lang._('Cloudflare Gateway — forward all DNS through your Zero Trust policy') }}</option>
                <option value="custom">{{ lang._('Custom — forward to specific DNS servers') }}</option>
            </select>
        </div>

        <div class="form-group" id="row-custom-servers" style="display:none;">
            <label for="dns-custom-servers">{{ lang._('Custom DNS Servers') }}</label>
            <input type="text" id="dns-custom-servers" class="form-control" style="max-width: 400px;"
                   placeholder="8.8.8.8, 8.8.4.4">
            <span class="help-block">{{ lang._('Comma-separated IPv4 or IPv6 addresses') }}</span>
        </div>

        <div class="form-group">
            <label for="dns-search-domains">{{ lang._('Search Domains') }}</label>
            <input type="text" id="dns-search-domains" class="form-control" style="max-width: 400px;"
                   placeholder="corp.example.com, internal.example.com">
            <span class="help-block">{{ lang._('Comma-separated domains — marked as insecure in Unbound (required for internal split-DNS zones)') }}</span>
        </div>

        <button id="btn-dns-save" class="btn btn-primary">
            <span class="fa fa-save"></span> {{ lang._('Save') }}
        </button>
        <span id="dns-save-result" style="display:none; margin-left:10px;"></span>

    </div>
</div>
