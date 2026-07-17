/* ghosttrap browser capture — posts uncaught errors and unhandled promise
   rejections to the same-origin relay (ghosttrap.django.js_report), which
   forwards them to ghosttrap.io. No token in the page.
   Override the relay path with <script ... data-endpoint="/custom/js/">. */
(function () {
  "use strict";
  var script = document.currentScript;
  var endpoint = (script && script.getAttribute("data-endpoint")) || "/ghosttrap/js/";
  var budget = 10; /* max reports per page load, so a hot loop can't storm */
  var seen = {};

  function junk(message, stack) {
    if (!message && !stack) return true;
    /* opaque cross-origin script errors carry no information */
    if (message === "Script error." && !stack) return true;
    /* browser extensions throw constantly and aren't ours to fix */
    if ((stack + message).indexOf("-extension://") !== -1) return true;
    return false;
  }

  function send(name, message, stack, kind) {
    name = name || "Error";
    message = message || "";
    stack = stack || "";
    if (budget <= 0 || junk(message, stack)) return;
    var key = name + "|" + message;
    if (seen[key]) return;
    seen[key] = true;
    budget--;
    var body = JSON.stringify({
      name: name,
      message: message,
      stack: stack,
      url: location.href,
      kind: kind
    });
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(endpoint, new Blob([body], { type: "application/json" }));
      } else {
        fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: body,
          keepalive: true
        });
      }
    } catch (e) {
      /* reporting must never break the page */
    }
  }

  window.addEventListener("error", function (event) {
    /* resource load failures dispatch a plain Event and don't bubble here;
       this listener only sees real ErrorEvents, but guard anyway */
    if (!event || typeof event.message !== "string") return;
    var err = event.error;
    send(err && err.name, event.message, err && err.stack, "error");
  });

  window.addEventListener("unhandledrejection", function (event) {
    var reason = event.reason;
    if (reason instanceof Error) {
      send(reason.name, reason.message, reason.stack, "unhandledrejection");
    } else {
      send("UnhandledRejection", String(reason), "", "unhandledrejection");
    }
  });
})();
