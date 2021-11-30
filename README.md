## Home Assistant component to monitor LibrePhotos instance

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

### Output
#### Workers sensor
- **State:** workers count
- **Attributes**: 

### Configuration
Create a sensor entry in your `configuration.yaml` with these configuration values:
- `platform`: `librephotos` (*required*)
- `host`: string, IP/URL of host LibrePhotos is running on *(required)*
- `username`: string, username to login to LibrePhotos *(required)*
- `password`: string, password for user *(required)*
- `port`: int, port of LibrePhotos instance *(optional, default=3000)*
- `refresh_interval`: int, seconds between each update *(optional, default=60)*
- `friendly_name`: string, name as displayed in HA *(optional, default=librephotos)*

#### Sample entry:
```Configuration.yaml:
  sensor:
    - platform: librephotos
      host: "https://nas.fritz.box"
      username: "admin"
      password: "verysecurepassword"
      port: 3001
      scan_interval: 5
```