#!/usr/bin/env python3
"""
Convert Swagger 2.0 OpenAPI spec to OpenAPI 3.0 format.

This script handles the main conversions needed:
- swagger: "2.0" -> openapi: "3.0.0"
- host/basePath/schemes -> servers
- securityDefinitions -> components/securitySchemes
- definitions -> components/schemas
- parameters -> components/parameters
- responses -> components/responses
- consumes/produces -> request/response content types
"""

import sys
import yaml
from pathlib import Path
from typing import Dict, Any, List


def convert_security_definitions(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Convert securityDefinitions to components.securitySchemes (OpenAPI 3.0)."""
    if 'securityDefinitions' not in spec:
        return {}

    security_schemes = {}
    for name, definition in spec['securityDefinitions'].items():
        scheme = definition.copy()

        # OAuth2 flow conversion
        if scheme.get('type') == 'oauth2':
            flow_type = scheme.pop('flow', 'application')
            flows = {}

            if flow_type == 'application':
                flows['clientCredentials'] = {
                    'tokenUrl': scheme.pop('tokenUrl', ''),
                    'scopes': scheme.pop('scopes', {})
                }
            elif flow_type == 'implicit':
                flows['implicit'] = {
                    'authorizationUrl': scheme.pop('authorizationUrl', ''),
                    'scopes': scheme.pop('scopes', {})
                }
            elif flow_type == 'password':
                flows['password'] = {
                    'tokenUrl': scheme.pop('tokenUrl', ''),
                    'scopes': scheme.pop('scopes', {})
                }
            elif flow_type == 'accessCode':
                flows['authorizationCode'] = {
                    'authorizationUrl': scheme.pop('authorizationUrl', ''),
                    'tokenUrl': scheme.pop('tokenUrl', ''),
                    'scopes': scheme.pop('scopes', {})
                }

            scheme['flows'] = flows

        security_schemes[name] = scheme

    return security_schemes


def convert_servers(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert host/basePath/schemes to servers array (OpenAPI 3.0)."""
    host = spec.get('host', 'api.example.com')
    base_path = spec.get('basePath', '/')
    schemes = spec.get('schemes', ['https'])

    servers = []
    for scheme in schemes:
        url = f"{scheme}://{host}{base_path}"
        servers.append({'url': url})

    return servers


def convert_operation(operation: Dict[str, Any], default_consumes: List[str], default_produces: List[str]) -> Dict[str, Any]:
    """Convert operation-level properties to OpenAPI 3.0."""
    converted = operation.copy()

    # Handle consumes -> requestBody.content
    consumes = converted.pop('consumes', default_consumes)
    if 'parameters' in converted:
        body_params = [p for p in converted['parameters'] if p.get('in') == 'body']
        if body_params:
            body_param = body_params[0]
            request_body = {
                'required': body_param.get('required', False),
                'content': {}
            }

            if 'description' in body_param:
                request_body['description'] = body_param['description']

            for content_type in consumes:
                request_body['content'][content_type] = {
                    'schema': body_param.get('schema', {})
                }

            converted['requestBody'] = request_body
            converted['parameters'] = [p for p in converted['parameters'] if p.get('in') != 'body']

    # Handle produces -> responses.content
    produces = converted.pop('produces', default_produces)
    if 'responses' in converted:
        for status, response in converted['responses'].items():
            if 'schema' in response:
                schema = response.pop('schema')
                response['content'] = {}
                for content_type in produces:
                    response['content'][content_type] = {'schema': schema}

    return converted


def convert_swagger_to_openapi3(swagger_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a complete Swagger 2.0 spec to OpenAPI 3.0."""
    openapi_spec = {
        'openapi': '3.0.0',
        'info': swagger_spec.get('info', {}),
        'servers': convert_servers(swagger_spec)
    }

    # Convert security definitions
    security_schemes = convert_security_definitions(swagger_spec)

    # Move definitions, parameters, responses to components
    components = {}
    if security_schemes:
        components['securitySchemes'] = security_schemes
    if 'definitions' in swagger_spec:
        components['schemas'] = swagger_spec['definitions']
    if 'parameters' in swagger_spec:
        components['parameters'] = swagger_spec['parameters']
    if 'responses' in swagger_spec:
        components['responses'] = swagger_spec['responses']

    if components:
        openapi_spec['components'] = components

    # Copy security requirements
    if 'security' in swagger_spec:
        openapi_spec['security'] = swagger_spec['security']

    # Copy tags
    if 'tags' in swagger_spec:
        openapi_spec['tags'] = swagger_spec['tags']

    # Copy externalDocs
    if 'externalDocs' in swagger_spec:
        openapi_spec['externalDocs'] = swagger_spec['externalDocs']

    # Copy x-google extensions
    for key, value in swagger_spec.items():
        if key.startswith('x-google-'):
            openapi_spec[key] = value

    # Convert paths
    if 'paths' in swagger_spec:
        default_consumes = swagger_spec.get('consumes', ['application/json'])
        default_produces = swagger_spec.get('produces', ['application/json'])

        openapi_spec['paths'] = {}
        for path, path_item in swagger_spec['paths'].items():
            converted_path_item = {}

            for method in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
                if method in path_item:
                    converted_path_item[method] = convert_operation(
                        path_item[method],
                        default_consumes,
                        default_produces
                    )

            # Copy parameters at path level
            if 'parameters' in path_item:
                converted_path_item['parameters'] = path_item['parameters']

            # Copy x-google-backend
            if 'x-google-backend' in path_item:
                converted_path_item['x-google-backend'] = path_item['x-google-backend']

            openapi_spec['paths'][path] = converted_path_item

    return openapi_spec


def main():
    if len(sys.argv) < 3:
        print("Usage: convert_openapi_to_v3.py <input-swagger2.yaml> <output-openapi3.yaml>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    print(f"Reading Swagger 2.0 spec from: {input_file}")
    with open(input_file, 'r') as f:
        swagger_spec = yaml.safe_load(f)

    print("Converting to OpenAPI 3.0...")
    openapi_spec = convert_swagger_to_openapi3(swagger_spec)

    print(f"Writing OpenAPI 3.0 spec to: {output_file}")
    with open(output_file, 'w') as f:
        yaml.dump(openapi_spec, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print("✓ Conversion complete!")
    print(f"\nConverted spec:")
    print(f"  - OpenAPI version: {openapi_spec['openapi']}")
    print(f"  - Servers: {len(openapi_spec.get('servers', []))}")
    print(f"  - Paths: {len(openapi_spec.get('paths', {}))}")
    if 'components' in openapi_spec:
        print(f"  - Components:")
        for component_type, items in openapi_spec['components'].items():
            print(f"    - {component_type}: {len(items)}")


if __name__ == '__main__':
    main()
