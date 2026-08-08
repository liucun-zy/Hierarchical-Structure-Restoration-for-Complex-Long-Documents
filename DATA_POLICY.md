# Data policy

This repository is intentionally source-only. It does not include company reports, PDFs, OCR output, converted Markdown, images, benchmark data, API responses, or credentials from the working directory used to develop the code.

Before adding any dataset, example, or test fixture, confirm all of the following:

- You have the right to redistribute it under the repository license.
- It contains no confidential, personal, or credential-bearing content.
- Its source and applicable license are documented.
- It is small enough to be practical for a public Git repository.

Use synthetic data whenever it can demonstrate the behavior. If a real dataset is required, publish retrieval instructions and license information instead of committing restricted files.

The optional image and LLM-assisted modes may transmit supplied document material to the endpoint configured by the user. Users are responsible for ensuring that this transfer is permitted.
