# Dataset provenance manifest

The datasets are not redistributed here; download them from the sources below. The SHA-256 is of each file's uncompressed content, so a reader can check that a download matches the bytes these audits read. No official checksums exist for these releases to compare against.

## UNSW-NB15

Source: GitHub mirror of the official training/testing partition: github.com/Nir-J/ML-Projects (UNSW-Network_Packet_Classification); official release at research.unsw.edu.au/projects/unsw-nb15-dataset; byte-identical to the copy Section 4 analyzed, whose file names are swapped (that copy's file named testing-set holds this training-set's bytes, Section 4.2)

Used for: Tables 5, 6; Section 4

| File | SHA-256 (uncompressed) |
|---|---|
| `UNSW_NB15_training-set.csv` | `bec7dd5ec88dc2a0ccc7a07879d338395ed7421750f675fd0339e07dfe0648fa` |
| `UNSW_NB15_testing-set.csv` | `734fe6642edf758f7c94d7d9149426b49d202fe8e7bf0bef47392489c3c0a559` |

## NSL-KDD

Source: GitHub mirror github.com/defcom17/NSL_KDD (KDDTrain+.txt, KDDTest+.txt); the headerless files were given the standard KDD'99 column names at download, so the checksum covers the header line

Used for: Tables 5, 6

| File | SHA-256 (uncompressed) |
|---|---|
| `KDDTrain+.csv` | `2bd6e8546141bff488d1e1849e5b5baea5bfe9f5ac2e552f387058146a470d80` |
| `KDDTest+.csv` | `953e8c5b82e99000d72ccd9cfcbc01dacc11ce7cdbdd257669d268264dfc7fe5` |

## CIC-IDS2017 (MachineLearningCSV)

Source: Hugging Face mirror huggingface.co/datasets/c01dsnap/CIC-IDS2017 of the official MachineLearningCSV.zip (www.unb.ca/cic/datasets/ids-2017.html)

Used for: Tables 5, 6

| File | SHA-256 (uncompressed) |
|---|---|
| `Monday-WorkingHours.pcap_ISCX.csv` | `852c4beb34eda186f32561fa79df7a0747e92e1a6535b01270820dd9ffe17f34` |
| `Tuesday-WorkingHours.pcap_ISCX.csv` | `52b8692ae8c7d2ed04671fe2b98335693c0a92c7ab157d8c8b534d6523080851` |
| `Wednesday-workingHours.pcap_ISCX.csv` | `893c27dc968bf7a8adef1689f90be55ca4a4dc3088fb63d6ff247ac56856df2a` |
| `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` | `d67066211fb1689c78406f1506f4c44704ecb92088353d5c96d96d6474eb819d` |
| `Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv` | `6bcda3857c2504676034e3ea57762d38393cc734cb377a726bd5cb153961b1b5` |
| `Friday-WorkingHours-Morning.pcap_ISCX.csv` | `53a41c24d570ea83b7ac55b2e94df94e7a8216aeb80a2af0246b6bc8bb543000` |
| `Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv` | `ca1824c51bfbb7b3c72290a11be04366ba8815878c6a1cc5c44cb1cee269e99b` |
| `Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv` | `6ff1580f5f81c0ae28a26f7631721018577f5f7c5e0feac28b795fcfe7b411ee` |

## CIC-IDS2017 (GeneratedLabelledFlows)

Source: official GeneratedLabelledFlows.zip from UNB CIC (www.unb.ca/cic/datasets/ids-2017.html), extracted and gzipped

Used for: Table 6a, Section 6.3

| File | SHA-256 (uncompressed) |
|---|---|
| `Monday-WorkingHours.pcap_ISCX.csv` | `96f26aea87d513073769b48ce204c2921791149e1c6225f7db65a3fed7973820` |
| `Tuesday-WorkingHours.pcap_ISCX.csv` | `ae9c88e10c41a8eb1ff454ae98bc513454925097d0b0b57180f94e79de445815` |
| `Wednesday-workingHours.pcap_ISCX.csv` | `ed538e85b84181e8897dedb3d37d365982f44b27eccd67c477581a8b65f3d170` |
| `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` | `e3deaff483d18b53b100a441dff9b8919416df8876b4edcc0f0d1e4bf48397d0` |
| `Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv` | `d74238e054023c8bd4d8056650463cadb25c100fb0e26ebd4272c07b5c022c4b` |
| `Friday-WorkingHours-Morning.pcap_ISCX.csv` | `c061cd98f39d8054aeaed6244a5129a20b3985983d0d022b860ae8aa07fe8d21` |
| `Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv` | `7e2ddaa80a5849ba629463296b6128436c161b4a32e8034bb5beae06b0c45e08` |
| `Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv` | `1f779b4f0d78f9225554c4de53b5a2c07912b60dcd136ee4c5c1d0d2496b7cc4` |

## CSE-CIC-IDS2018

Source: official AWS S3 bucket cse-cic-ids2018, folder 'Processed Traffic Data for ML Algorithms'

Used for: Tables 5, 6, 6a, 6b

| File | SHA-256 (uncompressed) |
|---|---|
| `Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv` | `acff8bc61376ee031d80878ee6099e0b1a87a1bd711d8068298421418c9f8147` |
| `Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv` | `fa2947a8256d81ee9103ae16139d62d0e17aa23e696ee80d9e76fb51c01c9c4b` |
| `Friday-16-02-2018_TrafficForML_CICFlowMeter.csv` | `1a4919faa0c49c7af97230b0c2d076eba23ee6dd81103a3801d51ac316355d8b` |
| `Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv` | `7287a4d7740a1dddbf330ceb2beb6a4889d33ba63674558a68b5eb50d16711df` |
| `Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv` | `a5f4a1c2689e0aa6566c03a58466de9c407c0be0cbd3cc69306544026611be04` |
| `Thursday-22-02-2018_TrafficForML_CICFlowMeter.csv` | `da33c927018274f9d49b145baa00e4ce0526c25b3b890b34c489e247b5e24544` |
| `Friday-23-02-2018_TrafficForML_CICFlowMeter.csv` | `d0a7f5059d9823b6e9b392b759e306481a3502d190dea7a1b5502ae079ea069b` |
| `Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv` | `f15e2a12304446058a0186c8ad67de2bd15735a9ba5c70c9a1f4c4242ab06771` |
| `Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv` | `b0534c5d7d8b41e03df71c6966c995d116a8ed28e61f377c8b14cdf5d28f4edf` |
| `Friday-02-03-2018_TrafficForML_CICFlowMeter.csv` | `d96f38e7496aba83475031e6fb8c6fdf1abf6aa1b71325a917798f3c7de93de1` |

## CICDDoS2019

Source: official CSV-01-12.zip (training day) and CSV-03-11.zip (testing day) from UNB CIC (www.unb.ca/cic/datasets/ddos-2019.html); each day's CSVs merged into one file (a stray LibreOffice lock file in CSV-03-11 excluded)

Used for: Tables 5, 6, 6a, Section 6.3

| File | SHA-256 (uncompressed) |
|---|---|
| `train-full.csv` | `819ee17d91e00c6ac98124550cb5f0dc10b4d16e1a5f779c556ca043784e9b68` |
| `test-full.csv` | `c981a6115889e61c19b4ac8e022970ef8e599e104a4e7ee383312c39c7e23b71` |

## ToN-IoT

Source: official Train_Test_Network.csv from UNSW (research.unsw.edu.au/projects/toniot-datasets)

Used for: Tables 5, 6, 6a, 6b

| File | SHA-256 (uncompressed) |
|---|---|
| `train_test_network.csv` | `26ddc513552de36de6428b2e578efaed2b57504c716dfba847cc0109a64e1974` |

## BoT-IoT

Source: OpenML dataset 42072 'bot-iot-all-features', deposited by the dataset's authors (the official 5%-reduced, all-features release), stored as parquet; checksum of the parquet file

Used for: Tables 5, 6, 6a, 6b

| File | SHA-256 (uncompressed) |
|---|---|
| `bot-iot-all-features.parquet` | `eacece166ebe94dee4a2c51bb00cce62ab6c14bea9377f477aa40003ce5b52e1` |
