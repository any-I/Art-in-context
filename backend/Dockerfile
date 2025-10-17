# Use an official Maven image to build the app
FROM maven:3.9.6-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn clean package -DskipTests

# Use a smaller Java image to run it
FROM eclipse-temurin:17-jdk
WORKDIR /app
COPY --from=build /app/target/backend-1.0-SNAPSHOT.jar app.jar

# Render will inject PORT; Spring Boot must use it
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
