#include <TMP36.h>

#define HEAT_1 7
#define HEAT_2 6
#define HEAT_3 5

#define THERMO_1 A0
#define THERMO_2 A1
#define THERMO_3 A2

#define LED_1 12
#define LED_2 11
#define LED_3 10

TMP36 thermo_1(THERMO_1, 5.0);
TMP36 thermo_2(THERMO_2, 5.0);
TMP36 thermo_3(THERMO_3, 5.0);

bool is_hot_1 = false;
bool is_hot_2 = false;
bool is_hot_3 = false;

float heat_time_1 = 0;
float heat_time_2 = 0;
float heat_time_3 = 0;

float temp_1;
float temp_2;
float temp_3;

bool is_heating_1 = true;
bool is_heating_2 = true;
bool is_heating_3 = true;

void setup() {
  pinMode(HEAT_1, OUTPUT);
  pinMode(HEAT_2, OUTPUT);
  pinMode(HEAT_3, OUTPUT);

  pinMode(LED_1, OUTPUT);
  pinMode(LED_2, OUTPUT);
  pinMode(LED_3, OUTPUT);

  Serial.begin(9600);
}

void loop() {
  temp_1 = thermo_1.getTempF();
  temp_2 = thermo_2.getTempF();
  temp_3 = thermo_3.getTempF();

  if (temp_1 > 110.0) {is_hot_1 = true;}
  if (temp_2 > 110.0) {is_hot_2 = true;}
  if (temp_3 > 110.0) {is_hot_3 = true;}

  if (is_hot_1) {heat_time_1 += .2; digitalWrite(LED_1, HIGH);}
  if (is_hot_2) {heat_time_2 += .2; digitalWrite(LED_2, HIGH);}
  if (is_hot_3) {heat_time_3 += .2; digitalWrite(LED_3, HIGH);}

  if (temp_1 > 143.0) {is_heating_1 = false;}
  if (temp_2 > 143.0) {is_heating_2 = false;}
  if (temp_3 > 143.0) {is_heating_3 = false;}
  
  if (temp_1 < 135.0) {is_heating_1 = true;}
  if (temp_2 < 135.0) {is_heating_2 = true;}
  if (temp_3 < 135.0) {is_heating_3 = true;}

  if (is_heating_1) {digitalWrite(HEAT_1, HIGH);}
  else {digitalWrite(HEAT_1, LOW);}
  if (is_heating_2) {digitalWrite(HEAT_2, HIGH);}
  else {digitalWrite(HEAT_2, LOW);}
  if (is_heating_3) {digitalWrite(HEAT_3, HIGH);}
  else {digitalWrite(HEAT_3, LOW);}

  delay(100);

  if (heat_time_1 > 5*60) {digitalWrite(LED_1, LOW);}
  if (heat_time_2 > 5*60) {digitalWrite(LED_2, LOW);}
  if (heat_time_3 > 5*60) {digitalWrite(LED_3, LOW);} 

  delay(100);

  Serial.print("time elapsed: "); Serial.print(heat_time_1);
  Serial.print(" temp1: "); Serial.print(temp_1);
  Serial.print(" temp2: "); Serial.print(temp_2);
  Serial.print(" temp3: "); Serial.println(temp_3);
}
