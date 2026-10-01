FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
# The JAR is assembled in CI before docker build is invoked (gradle assemble --no-daemon)
COPY build/libs/ libs/
LABEL org.opencontainers.image.title="kotlin-core"
LABEL org.opencontainers.image.description="MyFriendsCore Kotlin shared library"
