const int RELAY_PIN = 8;
void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "ON") digitalWrite(RELAY_PIN, HIGH);
    else if (cmd == "OFF") digitalWrite(RELAY_PIN, LOW);
    else if (cmd == "TOGGLE") digitalWrite(RELAY_PIN, !digitalRead(RELAY_PIN));
  }
}
