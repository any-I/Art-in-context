import "slick-carousel/slick/slick.css";
import "slick-carousel/slick/slick-theme.css";
import React from "react";
import Slider from "react-slick";
import { FaChevronLeft, FaChevronRight } from "react-icons/fa";
import artistData from "./artistList";

function NextArrow({ onClick }) {
    return (
        <div
            onClick={onClick}
            onKeyUp={(e) => {
                if(e.key === "Enter"){
                    onClick();
                }
            }}
            tabIndex={0}
            aria-label = {"Carousel previous arrow"}
            role="button"
            className="flex items-center justify-center bg-yellow-500 rounded-full w-10 h-10 cursor-pointer hover:bg-yellow-400 absolute top-1/2 right-4 transform -translate-y-1/2 z-10 transition duration-250 ease"
        >
            <FaChevronRight className="text-white text-lg" />
        </div>
    );
}

function PrevArrow({ onClick }) {
    return (
        <div
            onClick={onClick}
            onKeyUp={(e) => {
                if(e.key === "Enter"){
                    onClick();
                }
            }}
            tabIndex={0}
            aria-label={"Carousel previous arrow"}
            role="button"
            className="flex items-center justify-center bg-yellow-500 rounded-full w-10 h-10 cursor-pointer hover:bg-yellow-400 absolute top-1/2 left-4 transform -translate-y-1/2 z-10 transition duration-250 ease"
        >
            <FaChevronLeft className="text-white text-lg" />
        </div>
    );
}

const carouselBreakpoints = [
    {
        breakpoint: 1250,
        settings: {
            slidesToShow: 6,
            slidesToScroll: 3,
            dots: true
        }
    },
    {
        breakpoint: 1000,
        settings: {
            slidesToShow: 5,
            slidesToScroll: 2,
            dots: true
        }
    },
    {
        breakpoint: 750,
        settings: {
            slidesToShow: 4,
            slidesToScroll: 2,
            dots: true
        }
    },
    {
        breakpoint: 600,
        settings: {
            slidesToShow: 3,
            slidesToScroll: 1,
            dots: false
        }
    }, 
    {
        breakpoint: 450,
        settings: {
            slidesToShow: 2,
            slidesToScroll: 1,
            dots: false
        }
    },
    {
        breakpoint: 375,
        settings: {
            slidesToShow: 1,
            slidesToScroll: 1,
            dots: false
        }
    }
];

function getInitialCarouselSettings(windowWidth){
    let ind = 0;
    while(ind < carouselBreakpoints.length && carouselBreakpoints[ind].breakpoint > windowWidth){
        ind++;
    }
    return carouselBreakpoints[Math.max(0, ind - 1)];
}

function Gallery( {setArtistName}) {
    const initSettings = getInitialCarouselSettings(window.innerWidth);
    const settings = {
        dots: true,
        infinite: true,
        speed: 500,
        slidesToShow: initSettings.settings.slidesToShow,
        slidesToScroll: initSettings.settings.slidesToScroll,
        dots: initSettings.settings.dots,
        dotsClass: "slick-dots", //default, but used in styling so make sure it's right
        nextArrow: <NextArrow />,
        prevArrow: <PrevArrow />,
        responsive: carouselBreakpoints,
        focusOnSelect: true
    };
    return (
        <div className="slider-container pb-5">
            <Slider {...settings}>
                {artistData.map((artist) => (
                    <div
                        onClick={() => {setArtistName(artist.name)}}
                        role="button"
                        title={artist.name + " (click to search)"}
                        className="artist-carousel-card bg-white w-full max-w-sm text-black rounded-xl cursor-pointer shadow-md overflow-hidden">
                        <div className="w-full aspect-[4/5]">
                            <img
                                src={artist.img}
                                alt={artist.name}
                                className="w-full h-full object-cover" />
                        </div>
                        <div>
                            <p
                                className="artist-carousel-name text-center font-bold mt-1 mb-2.5"
                            >{artist.name}</p>
                            {/*<button*/}
                            {/*    className="text-sm bg-green-800 hover:bg-green-700 mx-auto block mt-3 mb-1"*/}
                            {/*    onClick={() => {setArtistName(artist.name)}}>*/}
                            {/*    Select to search*/}
                            {/*</button>*/}
                        </div>
                    </div>
                ))}
            </Slider>
        </div>
    );
}

export default Gallery;
