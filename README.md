# Raphael Miyoyo

Software engineer in Nairobi. I grew up on the shores of Lake Victoria, and for eight years I've been building the systems that move money, data and goods: payments, warehouse integrations and the data pipelines between them.

## Now

- **Senior software engineer**, working remotely for a German logistics company on warehouse-management integrations.
- **Product lead at [Wrangla360](https://app.wrangla360.com)**.
- **Mentor at [Microverse](https://www.microverse.org)**, since 2023.
- **Learning Go** by building in the open: [kenya-geo](https://github.com/rmiyoyo/kenya-geo) and [Mapping Kenya](https://mapping-kenya.onrender.com).

## Open source

**[kenya-geo](https://github.com/rmiyoyo/kenya-geo)** is a Go package with Kenya's 47 counties, 1,450 wards and 890 post offices, 2019 census figures and boundaries. It finds the ward for any coordinate, parses postal addresses and serves it all as a JSON API. No dependencies outside the standard library. [Docs on pkg.go.dev](https://pkg.go.dev/github.com/rmiyoyo/kenya-geo).

```go
geo := kenyageo.Default()
ward, _ := geo.WardAt(-1.2884, 36.8233)
fmt.Println(ward.Name, ward.Constituency) // NAIROBI CENTRAL Starehe
```

**[Mapping Kenya](https://mapping-kenya.onrender.com)** is a website built on it: county maps shaded by population, electricity, internet use, religion and more, with a page for every county, constituency and ward. ([source](https://github.com/rmiyoyo/mapping-kenya))

## What I work with

**Daily:** PHP and Laravel, Python, MySQL, Google Cloud.<br>
**Payments:** M-Pesa, Pesapal, KopoKopo, Paystack.<br>
**Learning:** Go, and Rust next.

## Get in touch

[LinkedIn](https://www.linkedin.com/in/raphael-miyoyo/) · [X](https://twitter.com/r_miyoyo) · [Portfolio](https://rmiyoyo.github.io/Personal-Portfolio-Website/) · [Email](mailto:miyoyogithub@gmail.com)

Happy to talk about payments in Africa, open data, or a project you care about.
