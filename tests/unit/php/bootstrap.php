<?php

/**
 * PHPUnit bootstrap: stub OPNsense framework classes so controllers can be
 * loaded and tested without a full OPNsense/Phalcon install.
 */

// ── OPNsense\Core ────────────────────────────────────────────────────────────

namespace OPNsense\Core {
    class Backend {
        /** @var callable|null Set in tests to intercept configdRun calls. */
        public static $stub = null;
        /** Last command passed to configdRun (for assertion). */
        public static string $lastCmd = '';

        public function configdRun(string $cmd): string {
            static::$lastCmd = $cmd;
            if (static::$stub !== null) {
                return call_user_func(static::$stub, $cmd);
            }
            return '';
        }
    }

    class Config {
        public static function getInstance(): self { return new self(); }
        public function save(): void {}
    }
}

// ── OPNsense\Base ────────────────────────────────────────────────────────────

namespace OPNsense\Base {
    /** Minimal request stub — configure isPost and postData in each test. */
    class RequestStub {
        public function __construct(
            private bool $isPost = true,
            private array $postData = []
        ) {}

        public function isPost(): bool { return $this->isPost; }

        public function getPost($key, $filter = null, $default = null): mixed {
            // Fall back to $_POST so OrganizationController's $_POST trick works.
            return $this->postData[$key] ?? ($_POST[$key] ?? $default);
        }
    }

    class ApiControllerBase {
        public RequestStub $request;
        public function __construct() {
            $this->request = new RequestStub();
        }
    }

    class ApiMutableModelControllerBase extends ApiControllerBase {
        protected static string $internalModelName = '';
        protected static string $internalModelClass = '';

        protected function searchBase(string $path, array $fields): array { return []; }
        protected function getBase(string $name, string $path, ?string $uuid): array { return []; }
        protected function addBase(string $name, string $path): array { return ['result' => 'saved']; }
        protected function setBase(string $name, string $path, ?string $uuid): array { return ['result' => 'saved']; }
        protected function delBase(string $path, ?string $uuid): array { return ['result' => 'deleted']; }
        protected function toggleBase(string $path, ?string $uuid, $enabled): array { return ['result' => 'toggled']; }
    }
}

// ── OPNsense\CloudflareZT ────────────────────────────────────────────────────

namespace OPNsense\CloudflareZT {
    class CloudflareZT {
        public object $general;
        /** Override in tests: '1' = enabled, '0' = disabled. */
        public static string $enabledValue = '1';

        public function __construct() {
            $enabled = static::$enabledValue;
            $this->general = new class($enabled) {
                public string $enabled;
                public function __construct(string $e) { $this->enabled = $e; }
                public function __toString(): string { return $this->enabled; }
            };
        }

        public function serializeToConfig(): void {}
    }
}

// ── Autoload controllers ─────────────────────────────────────────────────────

namespace {
    $controllerDir = __DIR__ . '/../../../net/cloudflare-zt/src/opnsense/mvc/app/controllers/OPNsense/CloudflareZT/Api';
    foreach (glob("{$controllerDir}/*.php") as $file) {
        require_once $file;
    }
}
