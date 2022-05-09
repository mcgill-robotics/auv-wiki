FROM node

EXPOSE 3000
ENV HOST 0.0.0.0
ENV PORT 3000
ENV RANETO_VERSION 0.17.0
ENV RANETO_INSTALL_DIR /opt/raneto

RUN cd /tmp \
    && curl -SLO "https://github.com/gilbitron/Raneto/archive/$RANETO_VERSION.tar.gz" \
    && mkdir -p $RANETO_INSTALL_DIR \
    && tar -xzf "$RANETO_VERSION.tar.gz" -C $RANETO_INSTALL_DIR --strip-components=1 \
    && rm "$RANETO_VERSION.tar.gz"

WORKDIR $RANETO_INSTALL_DIR
RUN rm -rf example/content
COPY content example/content 
COPY config.default.js  example/config.default.js 
RUN npm install

CMD ["npm", "start"]
