/*
 * MusicArk Yandex upload runtime instrumentation.
 *
 * This script is intended for manual/local injection into the already-authenticated
 * official Yandex Music renderer through Chromium DevTools Protocol. It emits only
 * module/export/method identifiers, argument/result shapes and credential-source
 * classifications. It never emits scalar values, headers, cookies, tokens, URLs,
 * request bodies or response bodies.
 */
(() => {
  "use strict";

  const PREFIX = "__MUSICARK_UPLOAD_TRACE__";
  const TARGET_MODULES = ["12690", "31322"];
  const PUBLIC_CLIENTS = new Set(["YandexMusicDesktopApp", "YandexMusicWebNext"]);
  const SENSITIVE_KEYS = [
    "authorization", "cookie", "token", "secret", "session", "csrf", "xsrf",
    "passport", "credential", "password", "signature"
  ];
  const wrapped = new WeakSet();

  function safeIdentifier(value) {
    const text = String(value || "");
    return /^[A-Za-z0-9_$.]{1,160}$/.test(text) ? text : "unknown";
  }

  function sensitiveName(name) {
    const lower = String(name || "").toLowerCase();
    return SENSITIVE_KEYS.some((item) => lower.includes(item));
  }

  function valueShape(value, depth = 0) {
    if (depth >= 4) return { type: "truncated" };
    if (value === null) return { type: "null" };
    if (Array.isArray(value)) {
      return {
        type: "array",
        length: value.length,
        item: value.length ? valueShape(value[0], depth + 1) : { type: "unknown" }
      };
    }
    const kind = typeof value;
    if (kind === "string") return { type: "string" };
    if (kind === "number") return { type: "number" };
    if (kind === "boolean") return { type: "boolean" };
    if (kind === "undefined") return { type: "undefined" };
    if (kind === "function") return { type: "function" };
    if (kind !== "object") return { type: kind };

    const keys = {};
    for (const key of Object.keys(value).slice(0, 80)) {
      if (sensitiveName(key)) {
        keys[key] = { type: "redacted-sensitive" };
      } else {
        let item;
        try { item = value[key]; } catch (_) { item = undefined; }
        keys[key] = valueShape(item, depth + 1);
      }
    }
    return { type: "object", keys };
  }

  function hasTruthyKey(value, target, depth = 0, seen = new WeakSet()) {
    if (!value || typeof value !== "object" || depth > 3) return false;
    if (seen.has(value)) return false;
    seen.add(value);
    for (const key of Object.keys(value).slice(0, 100)) {
      let item;
      try { item = value[key]; } catch (_) { continue; }
      if (key === target && Boolean(item)) return true;
      if (item && typeof item === "object" && hasTruthyKey(item, target, depth + 1, seen)) return true;
    }
    return false;
  }

  function credentialSource(args) {
    for (const arg of args) {
      if (!arg || typeof arg !== "object") continue;
      if (hasTruthyKey(arg, "customApiToken")) return "custom-api-token";
      if (hasTruthyKey(arg, "oauthToken") || hasTruthyKey(arg, "accessToken") || hasTruthyKey(arg, "accountToken")) {
        return "account-oauth";
      }
      if (hasTruthyKey(arg, "sessionId") || hasTruthyKey(arg, "session")) return "session";
    }
    return "unknown";
  }

  function clientRemoteType(args) {
    for (const arg of args) {
      if (!arg || typeof arg !== "object") continue;
      const stack = [arg];
      const seen = new WeakSet();
      let budget = 100;
      while (stack.length && budget-- > 0) {
        const current = stack.pop();
        if (!current || typeof current !== "object" || seen.has(current)) continue;
        seen.add(current);
        for (const key of Object.keys(current).slice(0, 80)) {
          let item;
          try { item = current[key]; } catch (_) { continue; }
          if (key === "clientRemoteType" && PUBLIC_CLIENTS.has(item)) return item;
          if (item && typeof item === "object") stack.push(item);
        }
      }
    }
    return "unknown";
  }

  function emit(payload) {
    try {
      console.log(PREFIX + JSON.stringify(payload));
    } catch (_) {
      // Instrumentation must never affect application control flow.
    }
  }

  function invocationPayload(label, args) {
    return {
      function: safeIdentifier(label),
      timestamp: Date.now() / 1000,
      clientRemoteType: clientRemoteType(args),
      authorizationSource: credentialSource(args),
      customApiPrefixSelected: args.some((arg) => hasTruthyKey(arg, "customApiPrefixUrl")),
      customApiTokenPathSelected: args.some((arg) => hasTruthyKey(arg, "customApiToken")),
      argumentShapes: args.map((arg) => valueShape(arg))
    };
  }

  function wrapCallable(container, key, label) {
    let original;
    try { original = container[key]; } catch (_) { return false; }
    if (typeof original !== "function" || wrapped.has(original)) return false;

    const proxy = new Proxy(original, {
      apply(target, thisArg, args) {
        emit(invocationPayload(label, args));
        const result = Reflect.apply(target, thisArg, args);
        if (result && typeof result.then === "function") {
          result.then(
            (value) => emit({ function: safeIdentifier(label), resultShape: valueShape(value), timestamp: Date.now() / 1000 }),
            () => emit({ function: safeIdentifier(label), resultShape: { type: "rejected" }, timestamp: Date.now() / 1000 })
          );
        } else {
          emit({ function: safeIdentifier(label), resultShape: valueShape(result), timestamp: Date.now() / 1000 });
        }
        return result;
      },
      construct(target, args, newTarget) {
        emit(invocationPayload(label + ".construct", args));
        return Reflect.construct(target, args, newTarget);
      }
    });
    wrapped.add(original);
    wrapped.add(proxy);
    try {
      container[key] = proxy;
      return container[key] === proxy;
    } catch (_) {
      return false;
    }
  }

  function wrapPrototype(value, moduleId, exportName) {
    if (typeof value !== "function" || !value.prototype) return;
    for (const name of Object.getOwnPropertyNames(value.prototype)) {
      if (name === "constructor") continue;
      const descriptor = Object.getOwnPropertyDescriptor(value.prototype, name);
      if (!descriptor || typeof descriptor.value !== "function" || descriptor.writable === false) continue;
      wrapCallable(value.prototype, name, `m${moduleId}.${exportName}.${name}`);
    }
  }

  function acquireRequire() {
    if (globalThis.__musicarkWebpackRequire) return globalThis.__musicarkWebpackRequire;
    const chunkKeys = Object.keys(globalThis).filter((key) => /^webpackChunk/.test(key));
    for (const key of chunkKeys) {
      const chunk = globalThis[key];
      if (!Array.isArray(chunk) || typeof chunk.push !== "function") continue;
      const marker = `musicark_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
      try {
        chunk.push([[marker], {}, (requireFn) => { globalThis.__musicarkWebpackRequire = requireFn; }]);
      } catch (_) {
        continue;
      }
      if (globalThis.__musicarkWebpackRequire) return globalThis.__musicarkWebpackRequire;
    }
    return null;
  }

  function instrumentModule(requireFn, moduleId) {
    let exportsObject;
    try { exportsObject = requireFn(Number(moduleId)); } catch (_) { return { moduleId, available: false }; }
    if (!exportsObject) return { moduleId, available: false };

    const exportNames = Object.keys(exportsObject).slice(0, 120);
    let wrappedCount = 0;
    for (const exportName of exportNames) {
      let value;
      try { value = exportsObject[exportName]; } catch (_) { continue; }
      wrapPrototype(value, moduleId, safeIdentifier(exportName));
      if (wrapCallable(exportsObject, exportName, `m${moduleId}.${safeIdentifier(exportName)}`)) wrappedCount += 1;
    }
    emit({
      function: "instrumentModule",
      moduleId: safeIdentifier(moduleId),
      resultShape: { type: "module", keys: Object.fromEntries(exportNames.map((name) => [safeIdentifier(name), { type: "export" }])) },
      timestamp: Date.now() / 1000
    });
    return { moduleId, available: true, wrappedCount };
  }

  const requireFn = acquireRequire();
  if (!requireFn) {
    emit({ function: "instrumentation", resultShape: { type: "webpack-require-unavailable" }, timestamp: Date.now() / 1000 });
    return;
  }

  const result = TARGET_MODULES.map((moduleId) => instrumentModule(requireFn, moduleId));
  emit({
    function: "instrumentation",
    resultShape: { type: "installed", keys: Object.fromEntries(result.map((item) => [safeIdentifier(item.moduleId), { type: item.available ? "available" : "unavailable" }])) },
    timestamp: Date.now() / 1000
  });
})();
