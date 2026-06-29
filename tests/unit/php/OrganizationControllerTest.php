<?php

use OPNsense\Base\RequestStub;
use OPNsense\Core\Backend;
use OPNsense\CloudflareZT\Api\OrganizationController;
use PHPUnit\Framework\TestCase;

class OrganizationControllerTest extends TestCase
{
    private OrganizationController $ctrl;
    private const VALID_UUID = '550e8400-e29b-41d4-a716-446655440000';

    protected function setUp(): void
    {
        Backend::$stub = null;
        Backend::$lastCmd = '';
        $_POST = [];
        $this->ctrl = new OrganizationController();
        $this->ctrl->request = new RequestStub(isPost: true);
    }

    public function testSetActionStripsApiTokenFromPostData(): void
    {
        $orgData = ['name' => 'Acme', 'account_id' => 'abc123', 'api_token' => 'secret-token'];
        $_POST['organization'] = $orgData;
        $this->ctrl->request = new RequestStub(isPost: true, postData: ['organization' => $orgData]);
        Backend::$stub = fn($cmd) => '';

        $this->ctrl->setAction(self::VALID_UUID);

        // api_token must not be in $_POST after the action runs
        $this->assertArrayNotHasKey('api_token', $_POST['organization'] ?? []);
    }

    public function testSetActionStoresTokenViaConfigd(): void
    {
        $orgData = ['name' => 'Acme', 'api_token' => 'my-secret'];
        $this->ctrl->request = new RequestStub(isPost: true, postData: ['organization' => $orgData]);
        $cmds = [];
        Backend::$stub = function($cmd) use (&$cmds) { $cmds[] = $cmd; return ''; };

        $this->ctrl->setAction(self::VALID_UUID);

        $secretCmd = array_values(array_filter($cmds, fn($c) => str_contains($c, 'setsecret')));
        $this->assertNotEmpty($secretCmd, 'setsecret must be called when api_token is present');
        $this->assertStringContainsString('org_apitoken_' . self::VALID_UUID, $secretCmd[0]);
        // Value must be base64-encoded, not raw
        $this->assertStringContainsString(base64_encode('my-secret'), $secretCmd[0]);
    }

    public function testSetActionSkipsTokenStorageWhenTokenAbsent(): void
    {
        $orgData = ['name' => 'Acme', 'account_id' => 'abc123'];
        $this->ctrl->request = new RequestStub(isPost: true, postData: ['organization' => $orgData]);
        $cmds = [];
        Backend::$stub = function($cmd) use (&$cmds) { $cmds[] = $cmd; return ''; };

        $this->ctrl->setAction(self::VALID_UUID);

        $secretCmds = array_filter($cmds, fn($c) => str_contains($c, 'setsecret'));
        $this->assertEmpty($secretCmds, 'setsecret must not be called when no api_token in POST');
    }

    public function testDelActionCleansUpSecrets(): void
    {
        $cmds = [];
        Backend::$stub = function($cmd) use (&$cmds) { $cmds[] = $cmd; return ''; };

        $this->ctrl->delAction(self::VALID_UUID);

        $delCmd = array_values(array_filter($cmds, fn($c) => str_contains($c, 'delsecret')));
        $this->assertNotEmpty($delCmd, 'delsecret must be called on org delete');
        $this->assertStringContainsString('org_apitoken_' . self::VALID_UUID, $delCmd[0]);
    }

    public function testValidatetokenRequiresPost(): void
    {
        $this->ctrl->request = new RequestStub(isPost: false);
        $r = $this->ctrl->validatetokenAction(self::VALID_UUID);
        $this->assertSame('failed', $r['result']);
    }

    public function testValidatetokenRejectsInvalidUuid(): void
    {
        foreach (['', 'bad', '../etc/passwd'] as $bad) {
            $r = $this->ctrl->validatetokenAction($bad);
            $this->assertSame('failed', $r['result'], "UUID '{$bad}' should be rejected");
        }
    }

    public function testValidatetokenReturnsDecodedResult(): void
    {
        Backend::$stub = fn($cmd) => json_encode(['result' => 'valid', 'status' => 'active']);
        $r = $this->ctrl->validatetokenAction(self::VALID_UUID);
        $this->assertSame('valid', $r['result']);
        $this->assertSame('active', $r['status']);
    }

    public function testValidatetokenHandlesNonJsonResponse(): void
    {
        Backend::$stub = fn($cmd) => 'error: token not found';
        $r = $this->ctrl->validatetokenAction(self::VALID_UUID);
        $this->assertSame('failed', $r['result']);
    }
}
