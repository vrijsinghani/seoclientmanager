



{
  "places": [
    {
      "formattedAddress": "367 Pitt St, Sydney NSW 2000, Australia",
      "displayName": {
        "text": "Mother Chu's Vegetarian Kitchen",
        "languageCode": "en"
      }
    },
    ...
  ],
  "nextPageToken": "AeCrKXsZWzNVbPzO-MRWPu52jWO_Xx8aKwOQ69_Je3DxRpfdjClq8Ekwh3UcF2h2Jn75kL6PtWLGV4ecQri-GEUKN_OFpJkdVc-JL4Q"
}

## Field Masking

Field masking is used to specify which fields to return in the response. This helps reduce unnecessary data transfer and processing. Use the `X-Goog-FieldMask` header to specify fields, e.g., `places.displayName,places.formattedAddress`.

## Optional Parameters

- **locationBias**: Define a search area using a circle or rectangle.
- **locationRestriction**: Restrict results to a specific area.
- **minRating**: Filter results by minimum user rating.
- **openNow**: Return only places open at the time of the query.
- **evOptions**: Filter for electric vehicle charging options.

## Best Practices

- Use field masks to limit the data returned and reduce costs.
- Avoid using wildcards (*) in production to prevent large data responses.
- Use location biasing or restrictions to improve result relevance.
- Test queries using the API Explorer to understand the API's behavior.

