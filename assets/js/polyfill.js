// 3T Reader compatibility shim for Qt WebEngine builds that advertise a newer
// Chromium version than the embedded V8 feature set actually supports.
//
// Polyfills:
//   - Map.getOrInsert / Map.getOrInsertComputed  (V8 13.6+ / Chrome 136+)
//   - WeakMap.getOrInsert / WeakMap.getOrInsertComputed
//   - Promise.withResolvers                       (V8 11.8+ / Chrome 119+)
(function () {
    function installMapHelpers(Ctor) {
        if (!Ctor || !Ctor.prototype) return;
        if (!Ctor.prototype.getOrInsert) {
            Object.defineProperty(Ctor.prototype, 'getOrInsert', {
                configurable: true,
                writable: true,
                value: function (key, defaultValue) {
                    if (!this.has(key)) this.set(key, defaultValue);
                    return this.get(key);
                }
            });
        }
        if (!Ctor.prototype.getOrInsertComputed) {
            Object.defineProperty(Ctor.prototype, 'getOrInsertComputed', {
                configurable: true,
                writable: true,
                value: function (key, computeFn) {
                    if (!this.has(key)) this.set(key, computeFn(key));
                    return this.get(key);
                }
            });
        }
    }
    installMapHelpers(globalThis.Map);
    installMapHelpers(globalThis.WeakMap);
    if (!Promise.withResolvers) {
        Promise.withResolvers = function () {
            var resolve, reject;
            var promise = new Promise(function (res, rej) {
                resolve = res;
                reject = rej;
            });
            return { promise: promise, resolve: resolve, reject: reject };
        };
    }
})();
