FROM swift:5.10 AS builder
WORKDIR /build
COPY . .
RUN swift build -c release

FROM swift:5.10
WORKDIR /app
COPY --from=builder /build/.build/release/ .
LABEL org.opencontainers.image.title="swift-core"
LABEL org.opencontainers.image.description="MyFriendsCore Swift shared library"
