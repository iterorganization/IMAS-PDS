/* Interactive highlighting for the coupling diagrams.
 *
 * ymmsl2svg draws each conduit as one or more <path class="conduit"> with no record of
 * which ports they join, so nothing in the markup ties a conduit to a component. We
 * recover that here, geometrically:
 *
 *   - Every port is a <use href="#port-..."> inside its component's
 *     <g class="ComponentBlock_group">, so a path endpoint landing on a port position
 *     identifies both the port and the component.
 *   - Conduits touching a *model* port are drawn as two segments: a stub on the model
 *     frame, and the duct run. The stub also starts port_size away from the port glyph,
 *     which is drawn outside the frame. So model ports get a looser tolerance, and
 *     segments meeting at a shared free end are chained into one conduit.
 *
 * Positions are compared in root-SVG coordinates via getCTM(), because components and
 * ducts each sit under their own translate().
 */
(function () {
  "use strict";

  // A component port sits exactly on its endpoint; ports are ~9 units apart, so this
  // stays well clear of the neighbour.
  var COMPONENT_TOLERANCE = 2.0;
  // A model port glyph is drawn port_size (7) outside the frame its stub starts on.
  var MODEL_TOLERANCE = 8.0;
  // Two segments of one conduit meet at exactly the same point.
  var JOIN_TOLERANCE = 0.5;

  function transformed(svg, element, x, y) {
    var point = svg.createSVGPoint();
    point.x = x;
    point.y = y;
    return point.matrixTransform(element.getCTM());
  }

  function indexPorts(svg) {
    return Array.prototype.map.call(
      svg.querySelectorAll('use[href^="#port-"]'),
      function (use) {
        var anchor = transformed(
          svg,
          use,
          parseFloat(use.getAttribute("x")),
          parseFloat(use.getAttribute("y"))
        );
        var group = use.closest("g.ComponentBlock_group");
        var rect = group && group.querySelector("rect.component");
        var title = use.querySelector("title");
        return {
          element: use,
          group: group,
          x: anchor.x,
          y: anchor.y,
          component: rect ? rect.id.replace(/^component-/, "") : null,
          name: title ? title.textContent : "",
        };
      }
    );
  }

  function resolvePort(ports, point) {
    var best = null;
    var bestDistance = Infinity;
    ports.forEach(function (port) {
      var distance = Math.hypot(port.x - point.x, port.y - point.y);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = port;
      }
    });
    if (!best) {
      return null;
    }
    var tolerance = best.component === null ? MODEL_TOLERANCE : COMPONENT_TOLERANCE;
    return bestDistance <= tolerance ? best : null;
  }

  function segmentsOf(svg, ports) {
    return Array.prototype.map.call(
      svg.querySelectorAll("path.conduit"),
      function (path) {
        var ctm = path.getCTM();
        var start = path.getPointAtLength(0).matrixTransform(ctm);
        var end = path.getPointAtLength(path.getTotalLength()).matrixTransform(ctm);
        return {
          path: path,
          ends: [
            { point: start, port: resolvePort(ports, start) },
            { point: end, port: resolvePort(ports, end) },
          ],
        };
      }
    );
  }

  /* Join segments that meet at a shared unresolved end, then keep the conduits whose
   * two remaining ends both landed on a port. Anything still ambiguous is dropped
   * rather than guessed at. */
  function chain(segments) {
    var open = [];
    segments.forEach(function (segment) {
      segment.ends.forEach(function (end) {
        if (!end.port) {
          open.push({ segment: segment, end: end });
        }
      });
    });

    var merged = new Map();
    segments.forEach(function (segment) {
      merged.set(segment, [segment]);
    });

    open.forEach(function (a) {
      open.forEach(function (b) {
        if (a === b || a.segment === b.segment) {
          return;
        }
        var distance = Math.hypot(
          a.end.point.x - b.end.point.x,
          a.end.point.y - b.end.point.y
        );
        if (distance > JOIN_TOLERANCE) {
          return;
        }
        var groupA = merged.get(a.segment);
        var groupB = merged.get(b.segment);
        if (groupA === groupB) {
          return; // Already joined; the pair is visited from both directions.
        }
        var group = groupA.concat(groupB);
        group.forEach(function (segment) {
          merged.set(segment, group);
        });
      });
    });

    var conduits = [];
    var seen = new Set();
    merged.forEach(function (group) {
      if (seen.has(group)) {
        return;
      }
      seen.add(group);
      var resolved = [];
      group.forEach(function (segment) {
        segment.ends.forEach(function (end) {
          if (end.port) {
            resolved.push(end.port);
          }
        });
      });
      if (resolved.length === 2) {
        conduits.push({
          paths: group.map(function (segment) {
            return segment.path;
          }),
          ports: resolved,
        });
      }
    });
    return conduits;
  }

  function clear(svg) {
    svg.classList.remove("cd-active");
    Array.prototype.forEach.call(
      svg.querySelectorAll(".cd-on, .cd-near"),
      function (element) {
        element.classList.remove("cd-on", "cd-near");
      }
    );
  }

  function highlight(svg, conduits, matches) {
    svg.classList.add("cd-active");
    conduits.forEach(function (conduit) {
      if (!matches(conduit)) {
        return;
      }
      conduit.paths.forEach(function (path) {
        path.classList.add("cd-on");
      });
      conduit.ports.forEach(function (port) {
        port.element.classList.add("cd-on");
        if (port.group) {
          port.group.classList.add("cd-near");
        }
      });
    });
  }

  function activate(svg) {
    var ports = indexPorts(svg);
    var conduits = chain(segmentsOf(svg, ports));
    if (!conduits.length) {
      return; // Nothing recovered: leave the diagram as a plain picture.
    }

    function bind(element, matches, onEnter, onLeave) {
      element.addEventListener("mouseenter", function (event) {
        event.stopPropagation();
        clear(svg);
        if (onEnter) {
          onEnter();
        }
        highlight(svg, conduits, matches);
      });
      element.addEventListener("mouseleave", function (event) {
        clear(svg);
        if (onLeave) {
          onLeave(event);
        }
      });
    }

    function showComponent(group) {
      var rect = group.querySelector("rect.component");
      if (!rect) {
        return;
      }
      var name = rect.id.replace(/^component-/, "");
      clear(svg);
      group.classList.add("cd-on");
      highlight(svg, conduits, function (conduit) {
        return conduit.ports.some(function (port) {
          return port.component === name;
        });
      });
    }

    Array.prototype.forEach.call(
      svg.querySelectorAll("g.ComponentBlock_group"),
      function (group) {
        if (!group.querySelector("rect.component")) {
          return;
        }
        group.addEventListener("mouseenter", function (event) {
          event.stopPropagation();
          showComponent(group);
        });
        group.addEventListener("mouseleave", function () {
          clear(svg);
        });
      }
    );

    ports.forEach(function (port) {
      bind(
        port.element,
        function (conduit) {
          return conduit.ports.indexOf(port) !== -1;
        },
        null,
        function (event) {
          // Ports sit inside their component's group, so moving the pointer from a port
          // glyph back onto the component body fires this mouseleave but no matching
          // mouseenter on the group -- mouseenter does not bubble and the pointer never
          // left the group. Restore the component highlight by hand.
          if (
            port.group &&
            event.relatedTarget &&
            port.group.contains(event.relatedTarget)
          ) {
            showComponent(port.group);
          }
        }
      );
    });
  }

  function init() {
    Array.prototype.forEach.call(
      document.querySelectorAll(".coupling-diagram svg"),
      activate
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
