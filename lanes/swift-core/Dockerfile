FROM swift:5.10 AS builder
WORKDIR /build
COPY . .
RUN swift build -c release

FROM ubuntu:22.04
WORKDIR /app
COPY --from=builder /build/.build/release/ ./
