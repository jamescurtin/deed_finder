# -*- coding: utf-8 -*-
"""Download documents from the Plymouth County Registry of Deeds (ROD)

The system used by the ROD to uniquely identify documents is Book and Page,
which stems from a historic practice of physically appending pages to an
archival book each time a new document was added to the record.

By providing a valid book and page number, this script will return a PDF
containing the relevant ROD document.
"""
import argparse
import os
import pathlib
import sys
import tempfile
from glob import glob
from time import sleep
from typing import Dict, Tuple

import requests
from fpdf import FPDF
from mypy_extensions import TypedDict
from requests.cookies import RequestsCookieJar
from requests.models import Response
from requests.sessions import Session
from splinter import Browser
from splinter.driver.webdriver.chrome import WebDriver

from gooey import Gooey, GooeyParser

TITLE: str = 'Plymouth County Registry of Deeds Downloader'
DEFAULT_SLEEP_TIME: float = 0.5
MAX_RETRIES: int = 2

BookParamsDict = TypedDict('BookParamsDict', {
    'dir': str,
    'bk': int,
    'pg': int,
    'curr': int,
    'tot': int,
})


def _resource_path(relative_path: str) -> str:
    """ Get absolute path to resource.

    Obtain the path to a resource, even after the app has been frozen by
    Pyinstaller.

    Args:
        relative_path (str): Path relative to the current file
    Returns:
        str: absolute path to resource
    """
    base_path = getattr(sys, '_MEIPASS',
                        os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def _go_to_search_page(browser: WebDriver, book: int) -> None:
    """Navigate to the correct search page.

    The books available on the ROD are split across two search pages. This
    returns the page of the appropriate search link given the requested book.

    Args:
        browser (WebDriver): Selenium browser
        book (int): The requested book number
    Returns:
        None
    """
    menu_id: str = 'Navigator1_SearchCriteria1_menuLabel'
    if book < 2393:
        search_button_id: str = 'Navigator1_SearchCriteria1_LinkButton02'
    else:
        search_button_id = 'Navigator1_SearchCriteria1_LinkButton01'
    # sleep to ensure the menu has a chance to load
    sleep(DEFAULT_SLEEP_TIME)
    browser.find_by_id(menu_id).first.mouse_over()
    browser.find_by_id(search_button_id).first.click()


def _fill_in_search_terms(browser: WebDriver, book: int, page: int) -> None:
    """Search for the requested book and page

    Args:
        browser (WebDriver): Selenium browser
        book (int): The requested book number
        page (int): The requested page number
    Returns:
        None
    """
    book_input_name: str = 'SearchFormEx1$ACSTextBox_Book'
    page_input_name: str = 'SearchFormEx1$ACSTextBox_PageNumber'
    search_button_id: str = 'SearchFormEx1_btnSearch'

    browser.fill(book_input_name, book)
    browser.fill(page_input_name, page)
    browser.find_by_id(search_button_id).first.click()


def _select_document(browser: WebDriver) -> None:
    """Selects the first search result based on the book and page

    Because a given book and page corresponds to a single record, we can safely
    return the first result and be sure it is the result that the user is
    looking for

    Args:
        browser (WebDriver): Selenium browser
    Returns:
        None
    """
    book_link_id: str = 'DocList1_GridView_Document_ctl02_ButtonRow_Book_0'
    view_image_id: str = 'TabController1_ImageViewertabitem'

    browser.find_by_id(book_link_id).first.click()
    sleep(DEFAULT_SLEEP_TIME)
    browser.find_by_id(view_image_id).first.click()
    # Wait for page to load
    sleep(2)
    # viewing the image opens a new tab/window, requiring Selenium to switch
    browser.windows.current = browser.windows.current.next


def _create_session(browser: WebDriver) -> Session:
    """Creates a session using the requests library

    Selenium isn't great at downlading files, but requests is much better.
    Downloading a file from the ROD site requires certain cookies, so we create
    a request session object that contains the same cookies at the Selenium
    browser that loaded the page originally.

    Args:
        browser (WebDriver): Selenium browser
    Returns:
        Session
    """
    cookies: Dict[str, str] = browser.cookies.all()
    session: Session = requests.Session()
    cookie_jar: RequestsCookieJar = session.cookies
    requests.utils.cookiejar_from_dict(cookies, cookiejar=cookie_jar)
    return session


def _get_number_of_pages(browser: WebDriver) -> int:
    """Fetch the number of pages in the requested document

    A book/page tells us where a document begins--but it doesn't tell us where
    it ends. The image viewer tells us which page we're currently viewing in
    the form "Page x of y" We grab "y" to determine the total number of pages
    we need to read.

    Args:
        browser (WebDriver): Selenium browser
    Returns:
        int: number of pages to read
    """
    page_number_id: str = 'ImageViewer1_lblPageNum'
    page_range: str = browser.find_by_id(page_number_id).first.value
    num_pages: int = int(page_range.split(' ')[-1])
    return num_pages


def _get_page_url(browser: WebDriver) -> str:
    """Get the URL of the image asset of a jpg image to download.

    By default, the image asset returned has very small dimensions. By changing
    the zoom parameter, we can get a higher resolution version of the image.

    Args:
        browser (WebDriver): Selenium browser
    Returns:
        str: URL of the image to download
    """
    image_id: str = 'ImageViewer1_docImage'
    # Image first loads as spinning GIF. Sleep for long enough so that real
    # photo has a chance to load
    sleep(2)
    image_url: str = browser.find_by_id(image_id)[0]['src']
    image_url = image_url.replace('ZOOM=1', 'ZOOM=6')
    return image_url


def _download_image(session: Session, image_url: str, directory: str,
                    img_name: str, img_range: Tuple[int, int]) -> None:
    """Download image to a designated directory

    Args:
        session (Session): requests session object, containing cookies from
            Selenium browser
        image_url (str): URL of image to download
        directory (str): Directory to save image to
        img_name (str): Name of image
        img_range (tuple): Tuple containing ints (current_page, total_pages)
    Returns:
        None
    """
    response: Response = session.get(image_url)
    file_path: str = os.path.join(directory, '{}.jpg'.format(img_name))
    with open(file_path, 'wb') as out_file:
        out_file.write(response.content)
    print('Downloaded page {} of {}'.format(img_range[0], img_range[1]))


def _go_to_next_page(browser: WebDriver) -> None:
    """Go to the next page in a document

    Args:
        browser (WebDriver): Selenium browser
    Returns:
        None
    """
    next_page_button_id: str = 'ImageViewer1_BtnNext'
    browser.find_by_id(next_page_button_id).first.click()
    # make sure the page has enough time to load
    sleep(DEFAULT_SLEEP_TIME)


def _create_pdf(image_dir: str, output_dir: str, pdf_name: str) -> None:
    """Combine all downloaded images into a single PDF

    Args:
        image_dir (str): Directory containing the image files
        output_dir (str): Directory where the output PDF should be saved
        pdf_name (str): What to name the PDF
    Returns:
        None
    """
    directory: str = os.path.join(image_dir, '*.jpg')
    # makes sure the images are in the correct order by page number
    images: list = sorted(glob(directory))
    output_path: str = '{}/{}'.format(output_dir, pdf_name)

    pdf: FPDF = FPDF(unit='in', format='letter')
    for image in images:
        pdf.add_page()
        pdf.image(image, 0, 0, 8.5, 11)
        os.remove(image)
    pdf.output(output_path, "F")


@Gooey(program_name=TITLE, image_dir=_resource_path('images'))
def get_book_and_page() -> argparse.Namespace:
    """Get user input to find a registry of deeds document. Also creates GUI.

    Args:
        None
    Returns:
        argparse.Namespace
    """
    parser = GooeyParser(
        description=(
            'Enter a book and page number, and a PDF of the document will '
            'be saved to a folder of your choice'))
    download_dir = parser.add_argument_group("Download location")
    download_dir.add_argument(
        'Directory',
        help="Select where to save the downloaded files",
        widget='DirChooser',
        type=str,
        default=os.path.join(pathlib.Path.home(), 'Downloads'))

    book_page = parser.add_argument_group("Deed Information")
    book_page.add_argument(
        'Book',
        type=int,
        help='Book number',
        gooey_options={
            'validator': {
                'test': 'int(user_input)',
                'message': 'Must be an integer'
            }
        })
    book_page.add_argument(
        'Page',
        type=int,
        help='Page number',
        gooey_options={
            'validator': {
                'test': 'int(user_input)',
                'message': 'Must be an integer'
            }
        })
    args = parser.parse_args()
    return args


def download_pdf(book: int, page: int, output_dir: str) -> None:
    """Given a book and page number, download a PDF document from the ROD

    Args:
        book (int): Book number
        page (int): Page number
        output_dir (str): Directory where the PDF should be saved
    Returns:
        None
    """
    print('Trying to obtain Book {} Page {}'.format(book, page))
    base_url: str = 'http://titleview.org/plymouthdeeds/'

    with tempfile.TemporaryDirectory() as page_download_dir:
        driver: str = _resource_path("chromedriver")
        browser: WebDriver = Browser(
            'chrome', executable_path=driver, headless=True)
        browser.visit(base_url)

        _go_to_search_page(browser, book)
        _fill_in_search_terms(browser, book, page)
        _select_document(browser)

        session: Session = _create_session(browser)

        current_page: int = 1
        total_pages: int = _get_number_of_pages(browser)
        while current_page <= total_pages:
            page_url: str = _get_page_url(browser)
            params: BookParamsDict = {
                'dir': page_download_dir,
                'bk': book,
                'pg': page,
                'curr': current_page,
                'tot': total_pages,
            }
            img_range: Tuple[int, int] = (current_page, total_pages)
            page_name: str = ('{dir}/bk_{bk:06d}_pg_{pg:06d}'
                              '_{curr:02d}_of_{tot:02d}')
            page_name = page_name.format(**params)

            _download_image(session, page_url, page_download_dir, page_name,
                            img_range)
            if current_page != total_pages:
                _go_to_next_page(browser)
            current_page += 1

        pdf_name: str = 'plymouth_cty_reg_deeds_book{:06d}_page{:06d}.pdf'
        pdf_name = pdf_name.format(book, page)
        _create_pdf(page_download_dir, output_dir, pdf_name)


def main() -> None:
    args: argparse.Namespace = get_book_and_page()

    book: int = args.Book
    page: int = args.Page
    download_dir: str = args.Directory
    retries: int = 0
    while retries <= MAX_RETRIES:
        try:
            download_pdf(book, page, download_dir)
            print('Success!')
            return
        except Exception as ex:
            print('Error! Retrying')
            print('Exception:\n{}\n'.format(ex))
            retries += 1
    raise ValueError('Unable to obtain document. Confirm the book and page '
                     'numbers entered are valid')


if __name__ == '__main__':
    main()
