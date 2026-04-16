FROM birtha/knowledge-eng-system:1.0.0
ENV DEBIAN_FRONTEND=noninteractive
USER root
COPY knowledge/coding-tools/runtime/docker/gui/install-gui-stack.sh /usr/local/bin/install-gui-stack
COPY knowledge/coding-tools/runtime/docker/gui/entrypoint.sh /usr/local/bin/knowledge-gui-entrypoint
COPY knowledge/coding-tools/runtime/docker/gui/healthcheck.sh /usr/local/bin/knowledge-gui-healthcheck
RUN chmod +x /usr/local/bin/install-gui-stack /usr/local/bin/knowledge-gui-entrypoint /usr/local/bin/knowledge-gui-healthcheck \
    && /usr/local/bin/install-gui-stack
ENV DISPLAY=:99
ENV VNC_PORT=5900
ENV NOVNC_PORT=6080
ENV SCREEN_GEOMETRY=1440x900x24
EXPOSE 6080
ENTRYPOINT ["tini", "--", "/usr/local/bin/knowledge-gui-entrypoint"]
CMD ["bash", "-lc", "xterm"]
