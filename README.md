## Home Assistant component to monitor LibrePhotos instance

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

### Output
#### Workers sensor
- **State**: workers count
- **Attributes**:
  - `workers[]`:
    - `id`: job ID
    - `job_type`: job type (e.g. 'Train faces')
    - `queued_by`: username of user who queued this job
    - `queued_at`: timestamp when job was queued
    - `started_at`: timestamp when job was started
    - `finished_at`: timestamp when job was finished
    - `is_started`: whether job has begun
    - `is_finished`: whether job is finished
    - `is_failed`: whether job has failed
    - `progress_current`: current job progress (e.g. **1**/10)
    - `progress_target`: current job goal (e.g. 1/**10**)
#### Statistics sensor
- **State**: number of total photos
- **Attributes**:
  - `stats`:
    - `num_photos`
    - `num_missing_photos`
    - `num_people`
    - `num_faces`
    - `num_unknown_faces`
    - `num_labeled_faces`
    - `num_inferred_faces`
    - `num_albumauto`: number of auto-generated albums (events)
    - `num_albumdate`
    - `num_albumuser`: number of manually created albums

### Configuration
Create a sensor entry in your `configuration.yaml` with these configuration values:
- `platform`: `librephotos` (*required*)
- `host`: string, IP/URL of host LibrePhotos is running on *(required)*
- `username`: string, username to login to LibrePhotos *(required)*
- `password`: string, password for user *(required)*
- `port`: int, port of LibrePhotos instance *(optional, default=3000)*
- `scan_interval`: int, seconds between each update *(optional, default=60)*

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