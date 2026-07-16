"""Unit tests for Plivo Tools"""

from unittest.mock import Mock, patch

from agno.tools.plivo import PlivoTools


class TestPlivoTools:
    """Test cases for PlivoTools"""

    @patch("plivo.RestClient")
    def test_initialization(self, mock_rest_client):
        """Test tool initialization and default tool registration"""
        mock_client = Mock()
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="test-auth-id", auth_token="test-auth-token")

        mock_rest_client.assert_called_once_with(auth_id="test-auth-id", auth_token="test-auth-token")
        assert tool.client == mock_client
        assert tool.name == "plivo"
        registered = {f.name for f in tool.functions.values()}
        assert {
            "send_sms",
            "make_call",
            "get_call_details",
            "list_messages",
            "send_verification",
            "validate_verification",
            "lookup_number",
            "send_whatsapp",
        } == registered

    @patch("plivo.RestClient")
    def test_enable_flags_gate_registration(self, mock_rest_client):
        """A method is only registered when its enable_ flag is on"""
        mock_rest_client.return_value = Mock()

        tool = PlivoTools(
            auth_id="id",
            auth_token="token",
            enable_send_sms=False,
            enable_make_call=False,
            enable_get_call_details=False,
            enable_list_messages=False,
            enable_validate_verification=False,
            enable_lookup_number=False,
            enable_send_whatsapp=False,
        )

        registered = {f.name for f in tool.functions.values()}
        assert registered == {"send_verification"}

    def test_validate_phone_number(self):
        """E.164 validation accepts valid numbers and rejects malformed ones"""
        assert PlivoTools.validate_phone_number("+14155551234") is True
        assert PlivoTools.validate_phone_number("14155551234") is False
        assert PlivoTools.validate_phone_number("+0155551234") is False
        assert PlivoTools.validate_phone_number("not-a-number") is False

    @patch("plivo.RestClient")
    def test_send_sms_success(self, mock_rest_client):
        """send_sms maps to Plivo's src/dst/text and returns the message UUID"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.message_uuid = ["abc-123"]
        mock_client.messages.create.return_value = mock_response
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.send_sms(to="+14155551234", from_="+14155550000", body="hello")

        mock_client.messages.create.assert_called_once_with(src="+14155550000", dst="+14155551234", text="hello")
        assert "abc-123" in result

    @patch("plivo.RestClient")
    def test_send_sms_rejects_non_e164(self, mock_rest_client):
        """send_sms fails closed on a non-E.164 recipient and never calls the API"""
        mock_client = Mock()
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.send_sms(to="14155551234", from_="+14155550000", body="hello")

        assert "E.164" in result
        mock_client.messages.create.assert_not_called()

    @patch("plivo.RestClient")
    def test_send_sms_allows_alphanumeric_sender(self, mock_rest_client):
        """src may be an alphanumeric sender ID or short code, not only an E.164 number"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.message_uuid = ["abc-123"]
        mock_client.messages.create.return_value = mock_response
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.send_sms(to="+14155551234", from_="PLIVO", body="hello")

        mock_client.messages.create.assert_called_once_with(src="PLIVO", dst="+14155551234", text="hello")
        assert "abc-123" in result

    @patch("plivo.RestClient")
    def test_make_call_success(self, mock_rest_client):
        """make_call maps to Plivo's from_/to_/answer_url/answer_method and returns the request UUID"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.request_uuid = "req-9"
        mock_client.calls.create.return_value = mock_response
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.make_call(
            to="+14155551234", from_="+14155550000", answer_url="https://example.com/answer.xml", answer_method="GET"
        )

        mock_client.calls.create.assert_called_once_with(
            from_="+14155550000", to_="+14155551234", answer_url="https://example.com/answer.xml", answer_method="GET"
        )
        assert "req-9" in result

    @patch("plivo.RestClient")
    def test_make_call_rejects_non_e164(self, mock_rest_client):
        """make_call fails closed on a non-E.164 recipient and never calls the API"""
        mock_client = Mock()
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.make_call(to="14155551234", from_="+14155550000", answer_url="https://example.com/answer.xml")

        assert "E.164" in result
        mock_client.calls.create.assert_not_called()

    @patch("plivo.RestClient")
    def test_make_call_rejects_bad_answer_method(self, mock_rest_client):
        """make_call rejects an answer_method other than GET/POST"""
        mock_client = Mock()
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.make_call(
            to="+14155551234", from_="+14155550000", answer_url="https://example.com/answer.xml", answer_method="DELETE"
        )

        assert "GET or POST" in result
        mock_client.calls.create.assert_not_called()

    @patch("plivo.RestClient")
    def test_list_messages_clamps_limit_to_plivo_max(self, mock_rest_client):
        """limit is clamped to Plivo's per-request max of 20 (the SDK rejects >20)"""
        mock_client = Mock()
        mock_client.messages.list.return_value = []
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        tool.list_messages(limit=100)

        mock_client.messages.list.assert_called_once_with(limit=20)

    @patch("plivo.RestClient")
    def test_send_verification_success(self, mock_rest_client):
        """send_verification creates a session and returns the session_uuid"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.session_uuid = "sess-1"
        mock_client.verify_session.create.return_value = mock_response
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.send_verification(to="+14155551234")

        mock_client.verify_session.create.assert_called_once_with(recipient="+14155551234", channel="sms")
        assert "sess-1" in result

    @patch("plivo.RestClient")
    def test_send_verification_rejects_non_e164(self, mock_rest_client):
        """send_verification fails closed on a non-E.164 recipient and never calls the API"""
        mock_client = Mock()
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.send_verification(to="14155551234")

        assert "E.164" in result
        mock_client.verify_session.create.assert_not_called()

    @patch("plivo.RestClient")
    def test_send_verification_rejects_bad_channel(self, mock_rest_client):
        """send_verification rejects a channel other than sms/voice"""
        mock_client = Mock()
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.send_verification(to="+14155551234", channel="carrier-pigeon")

        assert "sms or voice" in result
        mock_client.verify_session.create.assert_not_called()

    @patch("plivo.RestClient")
    def test_validate_verification_reports_verified_only_on_success_message(self, mock_rest_client):
        """validate_verification treats the code as valid only on the success message"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.message = "session validated successfully"
        mock_client.verify_session.validate.return_value = mock_response
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.validate_verification(session_uuid="sess-1", otp="123456")

        mock_client.verify_session.validate.assert_called_once_with("sess-1", otp="123456")
        assert result.startswith("verified")

    @patch("plivo.RestClient")
    def test_validate_verification_not_verified_on_other_message(self, mock_rest_client):
        """A non-success message is reported as not verified, never a false positive"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.message = "incorrect otp"
        mock_client.verify_session.validate.return_value = mock_response
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.validate_verification(session_uuid="sess-1", otp="000000")

        assert result.startswith("not verified")

    @patch("plivo.RestClient")
    def test_validate_verification_fails_closed_on_error(self, mock_rest_client):
        """A wrong or expired code surfacing as an SDK error is reported as not verified"""
        from plivo.exceptions import ValidationError

        mock_client = Mock()
        mock_client.verify_session.validate.side_effect = ValidationError("invalid")
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.validate_verification(session_uuid="sess-1", otp="000000")

        assert result.startswith("not verified")

    @patch("plivo.RestClient")
    def test_lookup_number_success(self, mock_rest_client):
        """lookup_number returns carrier and line-type details from nested dict fields"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.phone_number = "+14155551234"
        mock_response.country = {"name": "United States", "iso2": "US"}
        mock_response.carrier = {"name": "Example Carrier", "type": "mobile", "ported": "false"}
        mock_response.format = {"international": "+1 415-555-1234"}
        mock_client.lookup.get.return_value = mock_response
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.lookup_number(number="+14155551234")

        mock_client.lookup.get.assert_called_once_with("+14155551234")
        assert result["country"] == "United States"
        assert result["carrier"] == "Example Carrier"
        assert result["type"] == "mobile"
        assert result["ported"] == "false"

    @patch("plivo.RestClient")
    def test_lookup_number_rejects_non_e164(self, mock_rest_client):
        """lookup_number fails closed on a non-E.164 number and never calls the API"""
        mock_client = Mock()
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.lookup_number(number="14155551234")

        assert "E.164" in result["error"]
        mock_client.lookup.get.assert_not_called()

    @patch("plivo.RestClient")
    def test_send_whatsapp_freeform_success(self, mock_rest_client):
        """send_whatsapp sends freeform text with type_ whatsapp and returns the UUID"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.message_uuid = ["wa-1"]
        mock_client.messages.create.return_value = mock_response
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.send_whatsapp(to="+14155551234", from_="+14155550000", body="hello")

        mock_client.messages.create.assert_called_once_with(
            src="+14155550000", dst="+14155551234", type_="whatsapp", text="hello"
        )
        assert "wa-1" in result

    @patch("plivo.RestClient")
    def test_send_whatsapp_template_success(self, mock_rest_client):
        """send_whatsapp builds a Template object and sends it with type_ whatsapp"""
        from plivo.utils.template import Template

        mock_client = Mock()
        mock_response = Mock()
        mock_response.message_uuid = ["wa-2"]
        mock_client.messages.create.return_value = mock_response
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        template = {
            "name": "sample_purchase_feedback",
            "language": "en_US",
            "components": [{"type": "body", "parameters": [{"type": "text", "text": "Alex"}]}],
        }
        result = tool.send_whatsapp(to="+14155551234", from_="+14155550000", template=template)

        assert mock_client.messages.create.call_count == 1
        _, kwargs = mock_client.messages.create.call_args
        assert kwargs["src"] == "+14155550000"
        assert kwargs["dst"] == "+14155551234"
        assert kwargs["type_"] == "whatsapp"
        assert isinstance(kwargs["template"], Template)
        assert kwargs["template"].name == "sample_purchase_feedback"
        assert "wa-2" in result

    @patch("plivo.RestClient")
    def test_send_whatsapp_requires_body_or_template(self, mock_rest_client):
        """send_whatsapp rejects a call with neither body nor template"""
        mock_client = Mock()
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.send_whatsapp(to="+14155551234", from_="+14155550000")

        assert "body or template" in result
        mock_client.messages.create.assert_not_called()

    @patch("plivo.RestClient")
    def test_send_whatsapp_rejects_non_e164(self, mock_rest_client):
        """send_whatsapp fails closed on a non-E.164 recipient and never calls the API"""
        mock_client = Mock()
        mock_rest_client.return_value = mock_client

        tool = PlivoTools(auth_id="id", auth_token="token")
        result = tool.send_whatsapp(to="14155551234", from_="+14155550000", body="hello")

        assert "E.164" in result
        mock_client.messages.create.assert_not_called()
