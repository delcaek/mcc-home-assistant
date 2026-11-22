# Build environment for the overlay APK (JDK 17 + Android SDK platform 23 + build-tools 34.0.0).
#   docker build -t mcc-overlay-build overlay
#   docker run --rm -v "$PWD":/repo mcc-overlay-build        (run from the repository root)
FROM eclipse-temurin:17-jdk
ARG CMDLINE_TOOLS=https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
ENV ANDROID_HOME=/opt/android-sdk
RUN apt-get update && apt-get install -y --no-install-recommends unzip curl python3 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p $ANDROID_HOME/cmdline-tools && curl -fsSL -o /tmp/ct.zip "$CMDLINE_TOOLS" \
 && unzip -q /tmp/ct.zip -d $ANDROID_HOME/cmdline-tools && mv $ANDROID_HOME/cmdline-tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
 && rm /tmp/ct.zip \
 && yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses >/dev/null \
 && $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platforms;android-23" "build-tools;34.0.0" >/dev/null
WORKDIR /repo
CMD ["bash", "overlay/build.sh"]
