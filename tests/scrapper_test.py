# from unittest.mock import Mock, patch

# # from hireme.utils.scrapper import clean_html, download_page


# class TestCleanHtml:
#     def test_clean_html_removes_script_tags(self):
#         html = "<html><body><p>Content</p><script>alert('test')</script></body></html>"
#         result = clean_html(html)
#         assert "alert" not in result
#         assert "Content" in result

#     def test_clean_html_removes_style_tags(self):
#         html = (
#             "<html><body><p>Content</p><style>body {color: red;}</style></body></html>"
#         )
#         result = clean_html(html)
#         assert "color: red" not in result
#         assert "Content" in result

#     def test_clean_html_removes_noscript_tags(self):
#         html = "<html><body><p>Content</p><noscript>Enable JS</noscript></body></html>"
#         result = clean_html(html)
#         assert "Enable JS" not in result
#         assert "Content" in result

#     def test_clean_html_preserves_text_content(self):
#         html = "<html><body><h1>Title</h1><p>Paragraph text</p></body></html>"
#         result = clean_html(html)
#         assert "Title" in result
#         assert "Paragraph text" in result

#     def test_clean_html_removes_extra_whitespace(self):
#         html = "<html><body><p>Line 1</p><p>Line 2</p></body></html>"
#         result = clean_html(html)
#         lines = result.split("\n")
#         assert all(line.strip() for line in lines)

#     def test_clean_html_with_nested_tags(self):
#         html = "<html><body><div><span>Nested content</span></div></body></html>"
#         result = clean_html(html)
#         assert "Nested content" in result

#     def test_clean_html_empty_body(self):
#         html = "<html><body></body></html>"
#         result = clean_html(html)
#         assert result == ""


# class TestDownloadPage:
#     @patch("lime.utils.scrapper.requests.get")
#     def test_download_page_success(self, mock_get):
#         mock_response = Mock()
#         mock_response.status_code = 200
#         mock_response.text = "<html><body><p>Test content</p></body></html>"
#         mock_get.return_value = mock_response

#         result = download_page("https://example.com")
#         assert result is not None
#         assert "Test content" in result

#     @patch("lime.utils.scrapper.requests.get")
#     def test_download_page_failure(self, mock_get):
#         mock_response = Mock()
#         mock_response.status_code = 404
#         mock_get.return_value = mock_response

#         result = download_page("https://example.com")
#         assert result is None

#     @patch("lime.utils.scrapper.requests.get")
#     def test_download_page_server_error(self, mock_get):
#         mock_response = Mock()
#         mock_response.status_code = 500
#         mock_get.return_value = mock_response

#         result = download_page("https://example.com")
#         assert result is None

#     @patch("lime.utils.scrapper.requests.get")
#     def test_download_page_with_scripts_removed(self, mock_get):
#         mock_response = Mock()
#         mock_response.status_code = 200
#         mock_response.text = (
#             "<html><body><p>Job listing</p><script>tracker()</script></body></html>"
#         )
#         mock_get.return_value = mock_response

#         result = download_page("https://jobs.example.com")
#         assert "Job listing" in result
#         assert "tracker" not in result

#     @patch("lime.utils.scrapper.requests.get")
#     def test_download_page_job_listing_format(self, mock_get):
#         mock_response = Mock()
#         mock_response.status_code = 200
#         mock_response.text = """
#         <html><body>
#             <h1>Software Engineer</h1>
#             <div class="location">San Francisco</div>
#             <div class="salary">$120k - $150k</div>
#             <div class="description">We are looking for...</div>
#         </body></html>
#         """
#         mock_get.return_value = mock_response

#         result = download_page("https://jobs.example.com/123")
#         assert "Software Engineer" in result
#         assert "San Francisco" in result
#         assert "$120k - $150k" in result
