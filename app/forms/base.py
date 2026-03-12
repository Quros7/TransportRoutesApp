from flask_wtf import FlaskForm


class PydanticForm(FlaskForm):
    """Base form class that integrates Pydantic validation."""

    def validate(self, extra_validators=None):
        """Override validate to use Pydantic validation."""
        # First run WTForms validation for CSRF and basic field validation
        if not super().validate(extra_validators=extra_validators):
            return False

        # Now validate with Pydantic
        try:
            # Subclasses should implement this method to return data for Pydantic model
            pydantic_data = self.get_pydantic_data()
            pydantic_model = self.get_pydantic_model()
            pydantic_model(**pydantic_data)
            return True
        except Exception as e:
            # Map Pydantic errors back to WTForms
            self.map_pydantic_errors(e.errors())
            return False

    def get_pydantic_data(self):
        """Subclasses should override this to return data dict for Pydantic model."""
        raise NotImplementedError

    def get_pydantic_model(self):
        """Subclasses should override this to return the Pydantic model class."""
        raise NotImplementedError

    def map_pydantic_errors(self, errors):
        """Map Pydantic validation errors back to WTForms fields."""
        for error in errors:
            field_path = error["loc"]
            if len(field_path) == 1:
                # Top-level field
                field_name = field_path[0]
                if hasattr(self, field_name):
                    getattr(self, field_name).errors.append(error["msg"])
            else:
                # Handle nested fields if needed
                self.handle_nested_error(field_path, error["msg"])

    def handle_nested_error(self, field_path, msg):
        """Handle nested field errors. Subclasses can override."""
        pass
