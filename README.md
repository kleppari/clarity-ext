# clarity-ext
NOTE: Work in progress (pre-alpha).

Provides a library for extending Clarity LIMS in a more developer-friendly way.

## Problem 
Any LIMS system needs to be scripted (extended), as any lab has its own workflows. One extension could
be to create a driver file for a robot when the user presses a button in a workflow step.

The Clarity LIMS server provides extensibility in the form of so called EPPs. These are basically
shell commands that can be run on certain events in the system.

To develop and validate these steps, the developer would need to change the configuration entry for the
script in the LIMS and then run the script manually through the LIMS.

## Solution
With this tool, the developer can instead:
  * Set a step up as required
  * Write an extension that should run in this step
  * Run (integration test) the extension from his development environment
  * All requests/responses are cached, so the integration test will run fast. Furthermore, the test
    can still be executed after the step has been deleted or altered. 
  * Extensions have access to extension context, which do most of the work. This way, the readability 
    and simplicity of the extensions increases, allowing non-developers to review and alter the code.

