<?php

use OPNsense\Base\RequestStub;
use OPNsense\Core\Backend;
use OPNsense\CloudflareZT\Api\ServiceController;
use OPNsense\CloudflareZT\CloudflareZT;
use PHPUnit\Framework\TestCase;

class ServiceControllerTest extends TestCase
{
    private ServiceController $ctrl;

    protected function setUp(): void
    {
        Backend::$stub = null;
        Backend::$lastCmd = '';
        CloudflareZT::$enabledValue = '1';
        $this->ctrl = new ServiceController();
    }

    private function asGet(): void
    {
        $this->ctrl->request = new RequestStub(isPost: false);
    }

    private function asPost(): void
    {
        $this->ctrl->request = new RequestStub(isPost: true);
    }

    public function testStartRequiresPost(): void
    {
        $this->asGet();
        $r = $this->ctrl->startAction();
        $this->assertSame('failed', $r['result']);
    }

    public function testStopRequiresPost(): void
    {
        $this->asGet();
        $r = $this->ctrl->stopAction();
        $this->assertSame('failed', $r['result']);
    }

    public function testRestartRequiresPost(): void
    {
        $this->asGet();
        $r = $this->ctrl->restartAction();
        $this->assertSame('failed', $r['result']);
    }

    public function testStartCallsConfigd(): void
    {
        $this->asPost();
        Backend::$stub = fn($cmd) => 'ok';
        $r = $this->ctrl->startAction();
        $this->assertSame('cloudflarezt start', Backend::$lastCmd);
        $this->assertSame('ok', $r['result']);
    }

    public function testStatusReturnsDisabledWhenModelDisabled(): void
    {
        CloudflareZT::$enabledValue = '0';
        Backend::$stub = fn($cmd) => 'running (1/1)';
        $this->ctrl = new ServiceController();
        $r = $this->ctrl->statusAction();
        $this->assertSame('disabled', $r['result']);
    }

    public function testStatusReturnsRunning(): void
    {
        Backend::$stub = fn($cmd) => 'running (1/1)';
        $r = $this->ctrl->statusAction();
        $this->assertSame('running', $r['result']);
    }

    public function testStatusReturnsStopped(): void
    {
        Backend::$stub = fn($cmd) => 'stopped';
        $r = $this->ctrl->statusAction();
        $this->assertSame('stopped', $r['result']);
    }

    public function testStartConnRejectsInvalidUuid(): void
    {
        $this->asPost();
        foreach (['', 'bad', '../etc/passwd', str_repeat('a', 36)] as $bad) {
            $r = $this->ctrl->startconnAction($bad);
            $this->assertSame('failed', $r['result'], "Expected failed for UUID: '{$bad}'");
        }
    }

    public function testStartConnAcceptsValidUuid(): void
    {
        $this->asPost();
        $uuid = '550e8400-e29b-41d4-a716-446655440000';
        Backend::$stub = fn($cmd) => 'ok';
        $r = $this->ctrl->startconnAction($uuid);
        $this->assertStringContainsString($uuid, Backend::$lastCmd);
        $this->assertSame('ok', $r['result']);
    }

    public function testStopConnRejectsInvalidUuid(): void
    {
        $this->asPost();
        $r = $this->ctrl->stopconnAction('not-valid');
        $this->assertSame('failed', $r['result']);
        $this->assertStringContainsString('Invalid UUID', $r['message']);
    }

    public function testStartConnRequiresPost(): void
    {
        $this->asGet();
        $r = $this->ctrl->startconnAction('550e8400-e29b-41d4-a716-446655440000');
        $this->assertSame('failed', $r['result']);
    }
}
