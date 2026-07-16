"""
OpenAPI documentation for Guardian of health API
"""

SWAGGER_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>FocusGuardian API</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.11.0/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            SwaggerUIBundle({
                url: "/api/docs/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true
            });
        }
    </script>
</body>
</html>
"""

# Standard Error Schema reused across endpoints
ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "error": {"type": "string", "example": "Invalid parameter value"},
        "status": {"type": "string", "example": "failed"}
    }
}

OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "FocusGuardian API",
        "version": "2.0.0",
        "description": "AI Health Assistant API for posture and eye fatigue monitoring",
        "contact": {
            "name": "FocusGuardian Team",
            "email": "team@focusguardian.ai"
        }
    },
    "servers": [
        {"url": "http://localhost:5000", "description": "Local development"},
        {"url": "https://api.focusguardian.ai", "description": "Production"}
    ],
    "paths": {
        "/api/status": {
            "get": {
                "tags": ["Status"],
                "summary": "Get current system status",
                "responses": {
                    "200": {
                        "description": "Current status detailed statistics",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "fps": {"type": "integer", "example": 30},
                                        "face_detected": {"type": "boolean", "example": True},
                                        "posture": {
                                            "type": "object",
                                            "properties": {
                                                "angle": {"type": "number", "example": 5.2},
                                                "is_slouching": {"type": "boolean", "example": False},
                                                "severity": {"type": "string", "enum": ["good", "warning", "critical"], "example": "good"}
                                            }
                                        },
                                        "eyes": {
                                            "type": "object",
                                            "properties": {
                                                "blinks": {"type": "integer", "example": 12},
                                                "is_closed": {"type": "boolean", "example": False}
                                            }
                                        },
                                        "session": {
                                            "type": "object",
                                            "properties": {
                                                "duration": {"type": "integer", "description": "Duration in seconds", "example": 1800},
                                                "slouches": {"type": "integer", "example": 3}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/command": {
            "post": {
                "tags": ["Control"],
                "summary": "Send a control command",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["command"],
                                "properties": {
                                    "command": {
                                        "type": "string", 
                                        "enum": ["pause", "resume", "reset", "report", "quit"],
                                        "example": "pause"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Command executed successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "paused"}
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid command provided",
                        "content": {
                            "application/json": {
                                "schema": ERROR_SCHEMA
                            }
                        }
                    }
                }
            }
        },
        "/api/history": {
            "get": {
                "tags": ["Data"],
                "summary": "Get historical data",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 100},
                        "description": "Number of records to return",
                        "required": False
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Historical timeline of user posture and warnings",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "timestamp": {"type": "string", "example": "2026-07-16T12:00:00Z"},
                                            "spine_angle": {"type": "number", "example": 18.4},
                                            "is_slouching": {"type": "boolean", "example": True},
                                            "severity": {"type": "string", "example": "warning"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/export": {
            "get": {
                "tags": ["Data"],
                "summary": "Export data as CSV",
                "responses": {
                    "200": {
                        "description": "CSV filecontaining monitoring history logs",
                        "content": {
                            "text/csv": {
                                "schema": {"type": "string", "format": "binary"}
                            }
                        }
                    }
                }
            }
        },
        "/api/voice/command": {
            "post": {
                "tags": ["Voice"],
                "summary": "Send a voice command mock",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["command"],
                                "properties": {
                                    "command": {
                                        "type": "string",
                                        "enum": ["status", "pause", "resume", "report", "reset", "quit", "help", "break"],
                                        "example": "break"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Voice command processed successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "voice_command_triggered"},
                                        "command": {"type": "string", "example": "break"}
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid voice command",
                        "content": {
                            "application/json": {
                                "schema": ERROR_SCHEMA
                            }
                        }
                    }
                }
            }
        }
    },
    "tags": [
        {"name": "Status", "description": "System status endpoints"},
        {"name": "Control", "description": "Control and execution endpoints"},
        {"name": "Data", "description": "Data history and CSV export endpoints"},
        {"name": "Voice", "description": "Voice recognition and mock command endpoints"}
    ]
}

