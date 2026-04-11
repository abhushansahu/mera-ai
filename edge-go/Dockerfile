FROM golang:1.22-alpine AS builder

WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN go build -o /bin/mera-edge main.go

FROM alpine:3.20
RUN adduser -D appuser
USER appuser
WORKDIR /app
COPY --from=builder /bin/mera-edge /app/mera-edge
EXPOSE 8081
ENTRYPOINT ["/app/mera-edge"]
