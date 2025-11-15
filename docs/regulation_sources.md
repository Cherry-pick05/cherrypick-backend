# Regulation Sources

> Skeleton document. Fill in with detailed source information per airline, country, and international authority.

## Overview
- Purpose: Track official websites, PDFs, and APIs used for regulation crawling.
- Scopes:
  - Airline
  - Country
  - International (ICAO / IATA)

## Airline Sources
| Code | Name | Base URL | Notes |
|------|------|----------|-------|
| KE | Korean Air | `https://www.koreanair.com/` | Carry-on: <https://www.koreanair.com/contents/plan-your-travel/baggage/carry-on-baggage>, Checked: <https://www.koreanair.com/contents/plan-your-travel/baggage/checked-baggage/free-baggage> |
| TW | T'way Air | `https://www.twayair.com/` | Cabin & checked baggage: <https://www.twayair.com/app/serviceInfo/contents/1148> |

## Country Sources
| Code | Country | Security URL | Customs URL | Notes |
|------|---------|--------------|-------------|-------|
| KR | Republic of Korea | [Incheon Airport - Prohibited Items](https://www.airport.kr/ap_en/1433/subview.do) | [Korea Customs Service](https://www.customs.go.kr/kcs/ad/TaxFreeLimitInOutline.do) | Includes prohibited items and duty-free allowances |
| US | United States | [TSA What Can I Bring?](https://www.tsa.gov/travel/security-screening/whatcanibring/all-list) | [CBP Know Before You Go](https://www.cbp.gov/travel/us-citizens/know-before-you-go) | TSA checkpoint rules + customs declaration guidance |
| JP | Japan | [Narita Airport - Liquid Restrictions](https://www.narita-airport.jp/ko/airportguide/security/liquid/) | [Japan Customs - Passenger Guide](https://www.customs.go.jp/english/summary/passenger.htm) | Include Narita, Haneda, Kansai resources |

### Detailed References

- **United States**
  - TSA Checkpoint Rules
    - Comprehensive item list: <https://www.tsa.gov/travel/security-screening/whatcanibring/all-list>
    - Liquids rule: <https://www.tsa.gov/travel/security-screening/liquids-aerosols-gels-rule?utm_source=chatgpt.com>
  - Hazardous materials (49 CFR / FAA PackSafe)
    - Lithium batteries: <https://www.faa.gov/hazmat/packsafe/lithium-batteries?utm_source=chatgpt.com>

- **Japan**
  - Tokyo
    - Narita International Airport
      - Liquids restriction: <https://www.narita-airport.jp/ko/airportguide/security/liquid/>
      - Dangerous items: <https://www.narita-airport.jp/ko/airportguide/security/master-sheet/#3.%ED%9D%A1%EC%97%B0%EC%9A%A9%20%EB%9D%BC%EC%9D%B4%ED%84%B0>, <https://www.narita-airport.jp/ko/airportguide/security/master-sheet/#4.%EB%8F%84%EA%B2%80%EB%A5%98>
    - Haneda Airport
      - Dangerous goods PDF: <https://www.mlit.go.jp/common/001425422.pdf>
      - Liquids poster: <https://www.mlit.go.jp/koku/03_information/13_motikomiseigen/poster.pdf>
  - Osaka
    - Kansai International Airport (add specific references when curated)

- **Korea**
  - Incheon International Airport prohibited items: <https://www.airport.kr/ap_en/1433/subview.do>

## International Documents
| Code | Name | Resource | Access Notes |
|------|------|----------|--------------|
| ICAO | ICAO Technical Instructions |  | |
| IATA | IATA Dangerous Goods Regulations | <https://www.iata.org/contentassets/6fea26dd84d24b26a7a1fd5788561d6e/dgr-67-en-2.3.a.pdf> | Latest editions may require membership |

**Reference Notes**
- International hazardous materials overview: <https://www.iata.org/contentassets/6fea26dd84d24b26a7a1fd5788561d6e/dgr-67-en-2.3.a.pdf>
- Internal summary of regulations under review: <https://www.notion.so/2a2889c6a3908069b4cef8adbb71c609?pvs=21>

## TODO
- Populate URLs and document references.
- Add update frequency and authentication requirements if applicable.
