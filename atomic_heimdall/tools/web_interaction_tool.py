from typing import Optional
from pydantic import Field, BaseModel

from atomic_agents.lib.base.base_tool import BaseTool, BaseToolConfig
import helium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


################
# INPUT SCHEMA #
################
class HeliumToolInputSchema(BaseModel):
    """
    Schema for input to the Helium web automation tool.
    """
    url: Optional[str] = Field(None, description="The URL to navigate to.")
    text_click: Optional[str] = Field(None, description="The text of a clickable element to click.")
    link_click: Optional[str] = Field(None, description="The text of a link element to click.")
    scroll_down: Optional[int] = Field(None, description="Number of pixels to scroll down.")
    scroll_up: Optional[int] = Field(None, description="Number of pixels to scroll up.")
    close_popups: bool = Field(True, description="Whether to close any visible popups.")
    search_text: Optional[str] = Field(None, description="The text to search for using Ctrl+F.")
    nth_result: Optional[int] = Field(1, description="Which occurrence to jump to (for Ctrl+F search).")
    go_back: bool = Field(False, description="Whether to go back to the previous page")
    get_page_source: bool = Field(False, description="Whether to return the page source")
    get_screenshot: bool = Field(False, description="Whether to return a base64 encoded screenshot")


####################
# OUTPUT SCHEMA(S) #
####################
class HeliumToolOutputSchema(BaseModel):
    """
    Schema for output of the Helium web automation tool.
    """
    result: str = Field(..., description="Result of the web automation action.")
    current_url: str = Field(None, description="The current URL.")
    screenshot: Optional[bytes] = Field(None, description="Bytes encoded screenshot of the page, if requested.")
    page_source: Optional[str] = Field(None, description="The page source, if requested.")


##############
# TOOL LOGIC #
##############
class HeliumToolConfig(BaseToolConfig):
    """
    Configuration for the HeliumTool.
    """
    headless: bool = False
    window_width: int = 1000
    window_height: int = 1000
    force_device_scale_factor: bool = True
    disable_pdf_viewer: bool = True
    window_position_x: int = 0
    window_position_y: int = 0


class HeliumTool(BaseTool):
    """
    Tool for performing web automation using Helium.
    """
    input_schema = HeliumToolInputSchema
    output_schema = HeliumToolOutputSchema
    driver: webdriver.Chrome = None  # Class-level driver

    def __init__(self, config: HeliumToolConfig = HeliumToolConfig()):
        super().__init__(config)
        self.headless = config.headless
        self.window_width = config.window_width
        self.window_height = config.window_height
        self.force_device_scale_factor = config.force_device_scale_factor
        self.disable_pdf_viewer = config.disable_pdf_viewer
        self.window_position_x = config.window_position_x
        self.window_position_y = config.window_position_y

    def initialize_driver(self) -> webdriver.Chrome:
        """Initialize the Selenium WebDriver."""
        chrome_options = webdriver.ChromeOptions()
        if self.force_device_scale_factor:
            chrome_options.add_argument("--force-device-scale-factor=1")
        chrome_options.add_argument(f"--window-size={self.window_width},{self.window_height}")
        if self.disable_pdf_viewer:
            chrome_options.add_argument("--disable-pdf-viewer")
        chrome_options.add_argument(f"--window-position={self.window_position_x},{self.window_position_y}")
        return helium.start_chrome(headless=self.headless, options=chrome_options)

    def _perform_action(self, params: HeliumToolInputSchema) -> HeliumToolOutputSchema:
        """
        Performs the web automation action based on the input parameters.

        Args:
            params (HeliumToolInputSchema): The input parameters for the tool.

        Returns:
            HeliumToolOutputSchema: The output of the tool.

        Raises:
            Exception: If an error occurs during the web automation.
        """
        if HeliumTool.driver is None:
            HeliumTool.driver = self.initialize_driver()

        result = ""
        screenshot = None
        page_source = None
        current_url = None

        try:
            if params.url:
                helium.go_to(params.url)
                result += f"Navigated to {params.url}. "
            if params.text_click:
                try:
                    helium.click(params.text_click)
                    result += f"Clicked on text '{params.text_click}'. "
                except LookupError as e:
                    result += f"Error: Could not find text '{params.text_click}': {e}. "
            if params.link_click:
                try:
                    helium.click(helium.Link(params.link_click))
                    result += f"Clicked on link '{params.link_click}'. "
                except LookupError as e:
                    result += f"Error: Could not find link '{params.link_click}': {e}. "
            if params.scroll_down:
                helium.scroll_down(params.scroll_down)
                result += f"Scrolled down by {params.scroll_down} pixels. "
            if params.scroll_up:
                helium.scroll_up(params.scroll_up)
                result += f"Scrolled up by {params.scroll_up} pixels. "
            if params.close_popups:
                webdriver.ActionChains(HeliumTool.driver).send_keys(Keys.ESCAPE).perform()
                result += "Closed popups. "
            if params.search_text:
                elements = HeliumTool.driver.find_elements(By.XPATH, f"//*[contains(text(), '{params.search_text}')]")
                if params.nth_result > len(elements):
                    result += f"Error: Match n°{params.nth_result} not found (only {len(elements)} matches found) for text '{params.search_text}'. "
                else:
                    result += f"Found {len(elements)} matches for '{params.search_text}'. "
                    if elements:
                        elem = elements[params.nth_result - 1]
                        HeliumTool.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                        result += f"Focused on element {params.nth_result} of {len(elements)} for text '{params.search_text}'. "
            if params.go_back:
                HeliumTool.driver.back()
                result += "Went back to the previous page. "

            current_url = HeliumTool.driver.current_url
            result += "Current URL retrieved. "
            if params.get_page_source:
                page_source = HeliumTool.driver.page_source
                result += "Page source retrieved. "
            if params.get_screenshot:
                png_bytes = HeliumTool.driver.get_screenshot_as_png()
                screenshot: bytes = png_bytes  # Return the raw bytes
                result += "Screenshot captured. "

        except Exception as e:
            #  Include the error message in the result.
            result = f"Error: {e}"
            print(result)  #  Print the error for debugging
        finally:
            return HeliumToolOutputSchema(result=result, screenshot=screenshot, page_source=page_source, current_url=current_url)

    def run(self, params: HeliumToolInputSchema) -> HeliumToolOutputSchema:
        """
        Runs the Helium tool.

        Args:
            params (HeliumToolInputSchema): The input parameters for the tool.

        Returns:
            HeliumToolOutputSchema: The output of the tool.
        """
        return self._perform_action(params)

    @classmethod
    def close_driver(cls):
        """
        Closes the Selenium WebDriver.
        """
        if cls.driver is not None:
            cls.driver.quit()
            cls.driver = None

    def __del__(self):
        """
        Ensure the driver is closed when the object is garbage collected.
        """
        HeliumTool.close_driver()


#################
# EXAMPLE USAGE #
#################
def main():
    from rich.console import Console
    from io import BytesIO
    from PIL import Image
    from image import DrawImage

    console = Console()
    # Example 1: Navigate to a URL and get screenshot
    tool_instance = HeliumTool(config=HeliumToolConfig(headless=True))
    input_data = HeliumToolInputSchema(
        url="https://www.example.com",
        get_screenshot=True,
        get_current_url=True
    )

    output = tool_instance.run(input_data)

    console.print(output.result)
    img = Image.open(BytesIO(output.screenshot))
    DrawImage(img, (100, 40)).draw_image()
    console.print(f"Current URL: {output.current_url}")

    # Example 2: Click a link
    input_data = HeliumToolInputSchema(
        url="https://www.example.com",
        link_click="More information...",
        get_current_url=True
    )

    output = tool_instance.run(input_data)
    console.print(output.result)
    console.print(f"Current URL: {output.current_url}")

    # Example 3: Scroll and search text
    input_data = HeliumToolInputSchema(
        url="https://en.wikipedia.org/wiki/Main_Page",
        get_page_source=True,
        scroll_down=500,
        search_text="Did you know",
    )

    output = tool_instance.run(input_data)
    console.print(output.result)
    console.print(f"Page source length: {len(output.page_source)}")
    console.print(f"Page source snippet: [italic]{output.page_source[:256]}...[/italic]")

    # Example 4: close driver
    HeliumTool.close_driver()

if __name__ == "__main__":
    main()
