# Stage 1: Build
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app

COPY gradlew .
COPY gradle gradle
COPY build.gradle settings.gradle ./

# Cache dependencies
RUN ./gradlew dependencies --no-daemon 2>/dev/null || true

COPY src src
RUN ./gradlew bootJar -x test --no-daemon

# Stage 2: Run
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

COPY --from=builder /app/build/libs/*.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]