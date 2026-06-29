<?php

use OPNsense\Base\RequestStub;
use OPNsense\Core\Backend;
use OPNsense\CloudflareZT\Api\ConnectionController;
use PHPUnit\Framework\TestCase;

class ConnectionControllerTest extends TestCase
{
    private ConnectionController $ctrl;
    private const VALID_UUID = '550e8400-e29b-41d4-a716-446655440000';

    protected function setUp(): void
    {
        Backend::$stub = null;
        Backend::$lastCmd = '';
        $this->ctrl = new ConnectionController();
        $this->ctrl->request = new RequestStub(isPost: true);
    }

    public function testRegisterRequiresPost(): void
    {
        $this->ctrl->request = new RequestStub(isPost: false);
        $r = $this->ctrl->registerAction(self::VALID_UUID);
        $this->assertSame('failed', $r['result']);
    }

    public function testRegisterRequiresUuid(): void
    {
        $r = $this->ctrl->registerAction(null);
        $this->assertSame('failed', $r['result']);
    }

    public function testRegisterRejectsInvalidUuid(): void
    {
        foreach (['bad', 'not-a-uuid', '../../../etc/passwd', str_repeat('f', 36)] as $bad) {
            $r = $this->ctrl->registerAction($bad);
            $this->assertSame('failed', $r['result'], "UUID '{$bad}' should be rejected");
            $this->assertStringContainsString('Invalid UUID', $r['message']);
        }
    }

    public function testRegisterAcceptsValidUuidAndParsesJson(): void
    {
        $payload = ['result' => 'ok', 'device_id' => 'abc-123', 'client_ipv4' => '100.96.0.5'];
        Backend::$stub = fn($cmd) => json_encode($payload);
        $r = $this->ctrl->registerAction(self::VALID_UUID);
        $this->assertSame('ok', $r['result']);
        $this->assertSame('abc-123', $r['device_id']);
        $this->assertStringContainsString(self::VALID_UUID, Backend::$lastCmd);
    }

    public function testRegisterHandlesNonJsonBackendResponse(): void
    {
        Backend::$stub = fn($cmd) => 'configd error: script not found';
        $r = $this->ctrl->registerAction(self::VALID_UUID);
        $this->assertSame('failed', $r['result']);
        $this->assertStringContainsString('configd error', $r['message']);
    }

    public function testEnrollRejectsInvalidUuid(): void
    {
        $r = $this->ctrl->enrollAction('bad-uuid');
        $this->assertSame('failed', $r['result']);
        $this->assertStringContainsString('Invalid UUID', $r['message']);
    }

    public function testEnrollAcceptsValidUuid(): void
    {
        Backend::$stub = fn($cmd) => json_encode(['result' => 'ok']);
        $r = $this->ctrl->enrollAction(self::VALID_UUID);
        $this->assertSame('ok', $r['result']);
        $this->assertStringContainsString(self::VALID_UUID, Backend::$lastCmd);
    }

    public function testConnstatusRejectsInvalidUuid(): void
    {
        $r = $this->ctrl->connstatusAction('../../bad');
        $this->assertSame('failed', $r['result']);
        $this->assertStringContainsString('Invalid UUID', $r['message']);
    }

    public function testConnstatusReturnsDecodedJson(): void
    {
        $payload = ['result' => 'ok', 'status' => 'connected', 'pid' => 1234];
        Backend::$stub = fn($cmd) => json_encode($payload);
        $r = $this->ctrl->connstatusAction(self::VALID_UUID);
        $this->assertSame('connected', $r['status']);
    }
}
